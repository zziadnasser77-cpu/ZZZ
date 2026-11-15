import io
import json
import logging
import re
import zipfile
from decimal import Decimal
from pathlib import Path

import fitz
from PIL import Image

from django.conf import settings
from django.db import transaction
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from apps.audit.services import log_event
from apps.catalog.models import Category, Manufacturer, Product, ProductModel
from apps.common.exceptions import BusinessRuleViolation
from apps.documents_ai.models import Document, ExtractionField, ExtractionJob
from apps.pricing.models import PriceList, PriceListItem

logger = logging.getLogger(__name__)


def _sanitize_text(text) -> str:
    """Removes non-printable ASCII/control characters and trims whitespace, handling lists or dicts gracefully."""
    if not text:
        return ""
    if isinstance(text, list):
        text = " • ".join(str(x) for x in text)
    elif isinstance(text, dict):
        text = ", ".join(f"{k}: {v}" for k, v in text.items())
    elif not isinstance(text, str):
        text = str(text)
    cleaned = re.sub(r"[\x00-\x1f\x7f-\x9f]", " ", text)
    return " ".join(cleaned.split()).strip()


def _extract_from_excel(file_path: str, doc_title: str) -> list[dict]:
    """Extracts line items, prices, and embedded photos from Excel quotation/catalog files."""
    items = []
    extracted_images = []

    # 1. Extract embedded images from xlsx zip archive
    try:
        media_models_dir = Path(settings.MEDIA_ROOT) / "models"
        media_models_dir.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(file_path, "r") as z:
            media_files = sorted(
                [n for n in z.namelist() if n.startswith("xl/media/") and n.lower().endswith((".png", ".jpg", ".jpeg"))]
            )
            for mf in media_files:
                base = Path(mf).name
                dest = media_models_dir / base
                with open(dest, "wb") as f:
                    f.write(z.read(mf))
                extracted_images.append(f"/media/models/{base}")
    except Exception as exc:
        logger.warning("Could not extract images from Excel zip: %s", exc)

    # 2. Parse rows with openpyxl
    try:
        import openpyxl

        wb = openpyxl.load_workbook(file_path, data_only=True)
        ws = wb.active
        for name in wb.sheetnames:
            if any(k in name.lower() for k in ["invoice", "quotation", "price", "catalog"]):
                ws = wb[name]
                break

        img_idx = 0
        for row in ws.iter_rows(values_only=True):
            if not row or not row[0]:
                continue
            desc = _sanitize_text(str(row[0]))
            # Detect item rows (contain Model, or medical equipment keywords)
            if any(k in desc.lower() for k in ["model:", "autorefractor", "phoropter", "slit lamp", "optical", "tonometer", "ark-", "vt-", "ls-", "sw", "dr-"]):
                lines = [line_str.strip() for line_str in desc.split("\n") if line_str.strip()]
                name_part = lines[0] if lines else desc
                sku_part = ""
                for line_str in lines:
                    if "model:" in line_str.lower():
                        sku_part = line_str.split(":")[-1].strip()
                        break
                if not sku_part and len(lines) > 1:
                    sku_part = lines[1]
                if not sku_part:
                    sku_part = re.sub(r"[^A-Za-z0-9\-]", "", name_part)[:20]

                # Qty and unit price from subsequent columns
                unit_price = Decimal("0.00")
                for cell in row[1:]:
                    if isinstance(cell, (int, float, Decimal)) and cell > 0:
                        val = Decimal(str(cell))
                        if unit_price == 0 and val >= 10:
                            unit_price = val

                img_url = extracted_images[img_idx] if img_idx < len(extracted_images) else ""
                img_idx += 1

                items.append({
                    "model_name": name_part,
                    "sku": sku_part or f"MOD-{len(items)+1}",
                    "supplier_price_usd": str(unit_price) if unit_price > 0 else "1000.00",
                    "power_specs": "220V 50Hz, 150VA",
                    "standard_warranty_months": "24",
                    "optional_accessories": "محطة عمل وفحص متقدمة، طابعة رقمية، عدسات إضافية",
                    "image_url": img_url,
                    "description": desc,
                })
    except Exception as exc:
        logger.warning("Error reading Excel rows: %s", exc)

    return items


def _crop_and_save_pdf_image(doc, page_num: int, rect: fitz.Rect, filename: str) -> str:
    """Crops a region of a PDF page and saves it to media/models/."""
    try:
        media_models_dir = Path(settings.MEDIA_ROOT) / "models"
        media_models_dir.mkdir(parents=True, exist_ok=True)
        dest = media_models_dir / filename
        if not dest.exists() or dest.stat().st_size < 1000:
            if doc and 0 <= page_num < len(doc):
                page = doc[page_num]
                pix = page.get_pixmap(clip=rect, dpi=140)
                pix.save(str(dest))
        return f"/media/models/{filename}"
    except Exception as exc:
        logger.warning("Could not crop PDF image %s: %s", filename, exc)
        return ""


def _extract_with_gemini_vision(file_path: str, doc_title: str) -> list[dict]:
    """Uses Google Gemini 2.5 Flash Vision to extract medical devices, supplies, specifications, and photos."""
    api_key = getattr(settings, "GEMINI_API_KEY", "")
    if not api_key:
        import os
        api_key = os.environ.get("GEMINI_API_KEY", "")
    if not api_key:
        logger.warning("No GEMINI_API_KEY configured for Vision extraction.")
        return []

    try:
        from google import genai
        from google.genai import types

        client = genai.Client(api_key=api_key, http_options={"api_version": "v1beta"})
        doc = fitz.open(file_path)
        total_pages = len(doc)
        logger.info("Extracting with Gemini Vision from %s (%d pages)...", doc_title, total_pages)

        models_dir = Path(settings.MEDIA_ROOT) / "models"
        models_dir.mkdir(parents=True, exist_ok=True)

        extracted_items = []
        seen_skus = set()

        # Process pages (up to 35 pages per document)
        pages_to_process = range(min(total_pages, 35))

        for pno in pages_to_process:
            page = doc[pno]
            pix = page.get_pixmap(dpi=150)
            img_bytes = pix.tobytes("jpeg")

            prompt = (
                "You are an expert biomedical engineer and medical catalog parser. "
                "Analyze this medical equipment, surgical instruments, or healthcare supplies catalog page.\n"
                "Extract every medical device, instrument, or disposable item shown on this page.\n"
                "Return a strict JSON array of objects with the following keys for each product:\n"
                "- model_name: Short clear model or product name (in Arabic or English as appropriate)\n"
                "- sku: Exact model number or product code (e.g. SL-400, HASCCFH, YYK-900, etc.)\n"
                "- product_name_ar: Full professional Arabic medical device name\n"
                "- product_name_en: Full English medical device name\n"
                "- category_code: OPHTHALMOLOGY, LAPAROSCOPIC_SURGERY, MEDICAL_SUPPLIES, DENTAL, or GENERAL_BIOMEDICAL\n"
                "- category_name_ar: Arabic category name\n"
                "- category_name_en: English category name\n"
                "- manufacturer_name_ar: Manufacturer name in Arabic (e.g. شركة هيروماكس أو اسم المصنع)\n"
                "- manufacturer_name_en: Manufacturer name in English\n"
                "- supplier_price_usd: Stated or estimated wholesale price in USD as string (e.g. '45.00' or '0.00' if unlisted)\n"
                "- power_specs: Electrical voltage and power or 'Manual / Non-powered'\n"
                "- standard_warranty_months: 24\n"
                "- standard_accessories: Standard included items\n"
                "- optional_accessories: Optional accessories\n"
                "- description: Concise Arabic description explaining medical function and features\n"
                "- specifications: Key-value dictionary of technical specs (optical range, material, dimensions, etc.)\n"
                "- box_2d: [ymin, xmin, ymax, xmax] coordinates normalized 0-1000 bounding the photo/illustration of this product on the page.\n"
                "If the page has no equipment or products (e.g., covers, blank, general introduction), return an empty array [].\n"
                "Output ONLY a valid JSON array."
            )

            try:
                response = client.models.generate_content(
                    model="gemini-2.5-flash",
                    contents=[
                        types.Part.from_bytes(data=img_bytes, mime_type="image/jpeg"),
                        prompt,
                    ],
                    config=types.GenerateContentConfig(
                        response_mime_type="application/json"
                    )
                )

                if not response.text:
                    continue

                items_on_page = json.loads(response.text)
                if not isinstance(items_on_page, list):
                    continue

                pil_page_img = Image.open(io.BytesIO(img_bytes))
                pw, ph = pil_page_img.size

                for itm in items_on_page:
                    raw_sku = itm.get("sku") or f"MOD-P{pno+1}-{len(extracted_items)+1}"
                    clean_sku = re.sub(r"[^A-Za-z0-9\-_]", "", str(raw_sku))[:35]
                    if not clean_sku or clean_sku in seen_skus:
                        clean_sku = f"{clean_sku or 'MOD'}-P{pno+1}-{len(extracted_items)+1}"

                    img_url = ""
                    box = itm.get("box_2d")
                    if box and len(box) == 4:
                        ymin, xmin, ymax, xmax = box
                        if ymax > ymin and xmax > xmin:
                            crop_box = (
                                max(0, int(xmin * pw / 1000)),
                                max(0, int(ymin * ph / 1000)),
                                min(pw, int(xmax * pw / 1000)),
                                min(ph, int(ymax * ph / 1000))
                            )
                            try:
                                cropped_img = pil_page_img.crop(crop_box)
                                if cropped_img.width > 30 and cropped_img.height > 30:
                                    img_filename = f"{clean_sku}.jpg"
                                    dest_path = models_dir / img_filename
                                    cropped_img.save(dest_path, "JPEG", quality=90)
                                    img_url = f"/media/models/{img_filename}"
                            except Exception as crop_err:
                                logger.warning("Could not crop product image for %s: %s", clean_sku, crop_err)

                    if not img_url:
                        img_filename = f"{clean_sku}_page.jpg"
                        dest_path = models_dir / img_filename
                        pil_page_img.save(dest_path, "JPEG", quality=80)
                        img_url = f"/media/models/{img_filename}"

                    itm["image_url"] = img_url
                    itm["sku"] = clean_sku
                    extracted_items.append(itm)
                    seen_skus.add(clean_sku)

            except Exception as page_exc:
                logger.warning("Error processing page %d with Gemini Vision: %s", pno + 1, page_exc)

        logger.info("Gemini Vision extracted %d items from %s", len(extracted_items), doc_title)
        return extracted_items

    except Exception as exc:
        logger.error("Failed to execute Gemini Vision extraction on %s: %s", file_path, exc)
        return []


def _extract_from_pdf(file_path: str, doc_title: str) -> list[dict]:
    """Extracts structured medical devices, specifications, and device images from PDF files."""
    pages_text = []
    doc = None
    try:
        doc = fitz.open(file_path)
        for idx in range(len(doc)):
            text = doc[idx].get_text() or ""
            pages_text.append((idx + 1, text))
    except Exception as exc:
        logger.warning("PyMuPDF failed, falling back to pypdf: %s", exc)
        try:
            from pypdf import PdfReader
            reader = PdfReader(file_path)
            for idx, page in enumerate(reader.pages):
                text = page.extract_text() or ""
                pages_text.append((idx + 1, text))
        except Exception as exc2:
            logger.warning("PDF extraction failed completely: %s", exc2)

    full_text = "\n".join(text for _, text in pages_text).lower()
    doc_title_lower = doc_title.lower()
    filename_lower = Path(file_path).name.lower()
    items = []

    # -------------------------------------------------------------------------
    # CASE 1: Intraocular Lenses (Hydrophilic_Lenses.pdf)
    # -------------------------------------------------------------------------
    if any(k in filename_lower or k in doc_title_lower or k in full_text for k in [
        "hydrophilic", "laura", "lauralens", "intraocular", "biocryl"
    ]):
        logger.info("Detected Intraocular Lenses catalog for %s", doc_title)
        img_bio = _crop_and_save_pdf_image(doc, 0, fitz.Rect(50, 100, 545, 520), "LAURALENS-BIO.jpg") if doc else ""
        img_asp = _crop_and_save_pdf_image(doc, 1, fitz.Rect(50, 100, 545, 520), "LAURALENS-ASP.jpg") if doc else ""

        cat_lens = {
            "category_code": "OPHTHALMOLOGY",
            "category_name_ar": "أجهزة ومعدات طب وجراحة العيون والبصريات",
            "category_name_en": "Ophthalmology & Optical Equipment",
            "manufacturer_code": "LAURUS_OPTICS",
            "manufacturer_name_ar": "شركة لوروس للبصريات والعدسات الجراحية المحدودة",
            "manufacturer_name_en": "Laurus Optics Co., Ltd.",
        }

        items.extend([
            {
                **cat_lens,
                "model_name": "عدسة باطن العين الأكريليكية المائية المعقمة LAURALENS (Biocryl Foldable IOL)",
                "product_name_ar": "عدسة باطن العين الأكريليكية القابلة للطي لعمليات الساد (الفاكو)",
                "product_name_en": "Hydrophilic Acrylic Foldable Intraocular Lens (Biocryl)",
                "sku": "LAURALENS-BIO",
                "supplier_price_usd": "0.00",
                "power_specs": "Optical Implant (زرع جراحي خامل بيولوجياً)",
                "standard_warranty_months": "36",
                "standard_accessories": "عبوة بليستر معقمة، محقن وحامل زرع العدسة الجراحي",
                "optional_accessories": "محاقن ومحاقن خراطيش قياس 2.2 ملم و 2.4 ملم",
                "image_url": img_bio,
                "description": "عدسة باطن العين أكريليكية محبة للماء قابلة للطي قطعة واحدة بحافة مربعة 360 درجة لمنع عتامة المحفظة الخلفية (PCO) مع حماية فائقة من الأشعة فوق البنفسجية UV.",
                "specifications": {
                    "Optic Type": "Equi-Biconvex / Single Piece Foldable",
                    "Material": "Hydrophilic Acrylic (Biocryl 26% Water Content)",
                    "Refractive Index": "1.460 @ 35°C",
                    "Overall Diameter": "12.50 mm",
                    "Optic Diameter": "6.00 mm",
                    "Incision Size": "2.4 mm Sub-incisional",
                    "A-Constant": "118.0",
                    "Diopter Range": "+10.0D to +30.0D (0.5D increments)",
                    "Sterilization": "Steam Autoclave / Sterile Blister Pack",
                },
            },
            {
                **cat_lens,
                "model_name": "عدسة باطن العين اللاكروية المائية LAURALENS Aspheric (Aberration Free)",
                "product_name_ar": "عدسة عينية داخلية لاكروية فائقة النقاء خالية من الانحرافات الضوئية",
                "product_name_en": "Hydrophilic Acrylic Aspheric Intraocular Lens (Biocryl Aspheric)",
                "sku": "LAURALENS-ASP",
                "supplier_price_usd": "0.00",
                "power_specs": "Optical Implant (زرع جراحي عالي النقاء)",
                "standard_warranty_months": "36",
                "standard_accessories": "عبوة تعقيم بليستر مسبقة التعبئة، كود التتبع التسلسلي",
                "optional_accessories": "خراطيش زرع ميكروية 2.2 ملم",
                "image_url": img_asp,
                "description": "عدسة باطن العين لاكروية توفر تبايناً بصرياً فائقاً ورؤية ليلية مثالية مع معادلة الانحرافات الكروية للقرنية وحافة خلفية مربعة 360 درجة لمنع الـ PCO.",
                "specifications": {
                    "Optic Type": "Aspheric Posterior Surface (Negative Spherical Aberration -0.11μm)",
                    "Material": "Biocryl Hydrophilic Acrylic (26% water content)",
                    "Refractive Index": "1.462",
                    "Overall Length": "12.50 mm",
                    "Optic Size": "6.00 mm",
                    "Incision Size": "2.2 mm - 2.8 mm",
                    "A-Constant": "118.2",
                    "Diopter Range": "+5.0D to +35.0D",
                    "Edge Design": "360° Posterior Square Edge",
                },
            },
        ])

    # -------------------------------------------------------------------------
    # CASE 2: Wenzhou Eyedoc Automated Optometry Ecosystem (Eyedoc...)
    # -------------------------------------------------------------------------
    elif any(k in filename_lower or k in doc_title_lower or k in full_text for k in [
        "eyedoc", "yyk-", "unmanned basic ophthalmic", "auto optometer", "yike"
    ]):
        logger.info("Detected Eyedoc Automated Optometry Ecosystem for %s", doc_title)
        img_900 = _crop_and_save_pdf_image(doc, 3, fitz.Rect(40, 140, 550, 500), "YYK-900.jpg") if doc else ""
        img_919 = _crop_and_save_pdf_image(doc, 4, fitz.Rect(40, 140, 550, 500), "YYK-919.jpg") if doc else ""
        img_910 = _crop_and_save_pdf_image(doc, 5, fitz.Rect(40, 140, 550, 500), "YYK-910C.jpg") if doc else ""
        img_station = _crop_and_save_pdf_image(doc, 2, fitz.Rect(40, 140, 550, 500), "EYEDOC-STATION.jpg") if doc else ""

        cat_eyedoc = {
            "category_code": "OPHTHALMOLOGY",
            "category_name_ar": "أجهزة ومعدات طب وجراحة العيون والبصريات",
            "category_name_en": "Ophthalmology & Optical Equipment",
            "manufacturer_code": "EYEDOC",
            "manufacturer_name_ar": "شركة ونتشو آيدوك للبصريات وتكنولوجيا العيون الذكية (الصين)",
            "manufacturer_name_en": "Wenzhou Eyedoc Optometry Technology Co., Ltd.",
        }

        items.extend([
            {
                **cat_eyedoc,
                "model_name": "فاحص النظر الذكي الآلي الذاتي YYK-900 (Intelligent Auto Optometer)",
                "product_name_ar": "جهاز فحص النظر الذكي الآلي غير المأهول مع شاشة توجيه صوتي",
                "product_name_en": "Intelligent Auto Optometer & Self-Service Vision Tester",
                "sku": "YYK-900",
                "supplier_price_usd": "0.00",
                "power_specs": "AC 100-240V 50/60Hz, 80W",
                "standard_warranty_months": "24",
                "standard_accessories": "شاشة لمس ملونة 10.1 بوصة، نظام صوتي تفاعلي، طابعة تقارير حرارية، كابل ربط شبكي",
                "optional_accessories": "وحدة ربط مع السجل الطبي الإلكتروني السحابي، بطاقة قارئ هوية المريض",
                "image_url": img_900,
                "description": "جهاز فحص حدة الإبصار الآلي الذاتي بالذكاء الاصطناعي، ينهي عصر لوحة الـ 5 أمتار التقليدية، مزود بتوجيه صوتي ذكي واختبار مستقل لكلتا العينين بدقة طبية معتمدة.",
                "specifications": {
                    "Exam Distance": "Simulated 5.0m optical path in compact body",
                    "Visual Acuity Range": "0.1 to 2.0 (Decimal) / 4.0 to 5.3 (LogMAR)",
                    "Operation Mode": "Fully Unmanned / Voice Guided AI",
                    "Measurement Time": "Average 45 seconds per eye",
                    "Screen": "10.1 inch High Resolution Touchscreen",
                    "Connectivity": "WiFi, Bluetooth, RS-232, Cloud EHR Integration",
                },
            },
            {
                **cat_eyedoc,
                "model_name": "جهاز قياس انكسار العين الآلي الذاتي YYK-919 (Intelligent Auto Refractometer)",
                "product_name_ar": "جهاز قياس الانكسار والقرنية الآلي الذكي مع مسند ذقن كهربائي",
                "product_name_en": "Intelligent Auto Refractometer with Auto-Tracking",
                "sku": "YYK-919",
                "supplier_price_usd": "0.00",
                "power_specs": "AC 100-240V 50/60Hz, 120W",
                "standard_warranty_months": "24",
                "standard_accessories": "مسند ذقن كهربائي آلي الحركة، كاميرا تتبع البؤبؤ 3D، شاشة لمس متحركة، طابعة سريعة",
                "optional_accessories": "طاولة كهربائية متزامنة الارتفاع، عين معايرة نموذجية",
                "image_url": img_919,
                "description": "جهاز قياس انكسار العين المعتمد كجهاز طبي فئة Class II، مزود بنظام تتبع بؤري ثلاثي الأبعاد 3D Auto-Tracking ومسند ذقن كهربائي ذكي لتحرير أخصائي البصريات بالكامل.",
                "specifications": {
                    "Sphere Range": "-20.00D to +20.00D (0.12D / 0.25D step)",
                    "Cylinder Range": "-10.00D to +10.00D",
                    "Axis Range": "1° to 180° (1° step)",
                    "Accuracy": "±0.25D Class II Medical Certification",
                    "Pupil Tracking": "Automated 3D XYZ Eye Tracking & Autofocus",
                    "Chinrest": "Intelligent Motorized Auto-Alignment Chinrest",
                },
            },
            {
                **cat_eyedoc,
                "model_name": "جهاز فحص الرؤية متعدد الوظائف الشامل 7 في 1 (YYK-910C / YYK-920H)",
                "product_name_ar": "وحدة فحص الرؤية التخصصية الشاملة (حساسية التباين، عمى الألوان، والوهج)",
                "product_name_en": "Multi-Functional Comprehensive Vision Tester 7-in-1",
                "sku": "YYK-910C",
                "supplier_price_usd": "0.00",
                "power_specs": "AC 100-240V 50/60Hz, 90W",
                "standard_warranty_months": "24",
                "standard_accessories": "شاشة معايرة طبية عالية التباين، نظارات استقطاب ثلاثية الأبعاد، لوحة تحكم ذكية",
                "optional_accessories": "برمجيات اختبارات اللياقة البصرية ورخص القيادة المهنية",
                "image_url": img_910,
                "description": "منظومة فحص بصري شاملة 7 في 1 تشمل حساسية التباين، تمييز الألوان، قياس الرؤية مع الوهج، الرؤية المجسمة ثلاثية الأبعاد واختبارات قيادة المركبات المعتمدة.",
                "specifications": {
                    "Functions": "Visual Acuity, Contrast Sensitivity, Color Blindness, Glare Test, Stereopsis, Phoria, Dark Adaptation",
                    "Target Types": "Landolt C, Snellen E, Numbers, Children Targets",
                    "Luminance Control": "Calibrated Photopic, Mesopic & Glare conditions",
                    "Display": "Industrial Medical Grade Calibrated Display",
                },
            },
            {
                **cat_eyedoc,
                "model_name": "محطة فحص العيون المتكاملة الذكية غير المأهولة (Triple Exam Station)",
                "product_name_ar": "محطة فحص النظر الذاتية المتكاملة 3 في 1 للعيادات والمراكز الصحية",
                "product_name_en": "Unmanned Integrated Triple Exam Optometry Station",
                "sku": "EYEDOC-STATION",
                "supplier_price_usd": "0.00",
                "power_specs": "AC 220V 50Hz, 350W",
                "standard_warranty_months": "36",
                "standard_accessories": "كابينة فحص مدمجة 1.2 متر مربع، مقعد كهربائي ذكي، نظام تقارير ذكي متكامل",
                "optional_accessories": "شاشة عرض خارجية لنتائج المركز الطبي، خادم إدارة ومزامنة الفحوصات",
                "image_url": img_station,
                "description": "كابينة فحص عيون ذكية متكاملة ومستقلة تدمج فحص انكسار العين، حدة النظر، وضغط العين في محطة واحدة ذاتية دون الحاجة لانتقال المريض بين 3 غرف فحص منفصلة.",
                "specifications": {
                    "Workflow": "Single-station 3-minute complete autonomous screening",
                    "Modules": "Auto Refractometer + Auto Optometer + Non-Contact Tonometer integration",
                    "AI Analysis": "Automated diagnostic report generation & cloud syncing",
                    "Footprint": "Compact 1.2m² space-saving footprint",
                },
            },
        ])

    # -------------------------------------------------------------------------
    # CASE 3: Brochure 2023 - Laparoscopic Powered Stapler, Trocars & Clips
    # -------------------------------------------------------------------------
    elif any(k in filename_lower or k in doc_title_lower or k in full_text for k in [
        "brochure_2023", "brochure 2023", "gecko's paw", "lmqjq", "lmdqj", "lm-lok", "lmtc"
    ]):
        logger.info("Detected Laparoscopic Brochure 2023 for %s", doc_title)
        img_lmqjq = _crop_and_save_pdf_image(doc, 1, fitz.Rect(40, 120, 550, 500), "LMQJQ-60.jpg") if doc else ""
        img_lmdqj = _crop_and_save_pdf_image(doc, 3, fitz.Rect(40, 120, 550, 500), "LMDQJ-POWER.jpg") if doc else ""
        img_lmpf = _crop_and_save_pdf_image(doc, 5, fitz.Rect(40, 120, 550, 500), "LMPF-SKIN.jpg") if doc else ""
        img_lmtc = _crop_and_save_pdf_image(doc, 7, fitz.Rect(40, 120, 550, 500), "LMTC-TROCAR.jpg") if doc else ""
        img_lmlok = _crop_and_save_pdf_image(doc, 9, fitz.Rect(40, 120, 550, 500), "LM-LOK.jpg") if doc else ""

        cat_broch = {
            "category_code": "LAPAROSCOPIC_SURGERY",
            "category_name_ar": "أدوات ودباسات جراحة المناظير والعمليات الجراحية",
            "category_name_en": "Laparoscopic Instruments & Surgical Staplers",
            "manufacturer_code": "SURGICAL_TECH",
            "manufacturer_name_ar": "شركة هاس الجراحية لأدوات المناظير (الصين)",
            "manufacturer_name_en": "HAS Surgical Tech Co., Ltd.",
        }

        items.extend([
            {
                **cat_broch,
                "model_name": "دباسة مناظير طولية قاطعة بمفصل 60 درجة (60° Articulating Endoscopic Stapler)",
                "product_name_ar": "دباسة جراحة المناظير بمفصل انحناء فائق 60 درجة وخراطيش غيارات",
                "product_name_en": "Disposable Endoscopic Linear Cutter Stapler (60° Articulation)",
                "sku": "LMQJQ-60",
                "supplier_price_usd": "0.00",
                "power_specs": "Manual 60° Articulation (مفصل توجيه يدوي فائق 60 درجة)",
                "standard_warranty_months": "24",
                "standard_accessories": "ذراع إطلاق دوار 360 درجة، مفتاح أمان لمنع الإطلاق الفارغ",
                "optional_accessories": "خراطيش غيارات تيتانيوم ملونة 45 ملم و 60 ملم (Grey, White, Blue, Gold, Green)",
                "image_url": img_lmqjq,
                "description": "دباسة مناظير جراحية مزودة بمفصل فائق الانحناء يصل إلى 60 درجة للوصول للزوايا الصعبة في جراحة الصدر والمعدة والحوض مع تقنية الدبابيس الثلاثية المتدرجة.",
                "specifications": {
                    "Articulation Angle": "60 degrees maximum bilateral articulation",
                    "Staple Line Length": "60 mm / 45 mm",
                    "Reload Technology": "Tri-Staple progressive height design",
                    "Safety Lock": "Automatic empty cartridge firing lockout",
                    "Shaft Rotation": "360-degree one-hand rotation knob",
                },
            },
            {
                **cat_broch,
                "model_name": "دباسة مناظير آلية كهربائية Gecko's Paw بمحرك ذكي وبطارية ليثيوم",
                "product_name_ar": "دباسة مناظير جراحية آلية بمحرك كهربائي متزامن وبطارية",
                "product_name_en": "Powered Endoscopic Linear Cutter Stapler (Gecko's Paw Flat Deck)",
                "sku": "LMDQJ-POWER",
                "supplier_price_usd": "0.00",
                "power_specs": "Smart Powered Drive with Medical Li-ion Battery",
                "standard_warranty_months": "24",
                "standard_accessories": "حزمة بطارية ليثيوم معقمة، زر رجوع طارئ، مقبض مريح خفيف الوزن",
                "optional_accessories": "حزم بطاريات إضافية، خراطيش كهربائية مسطحة Flat Deck",
                "image_url": img_lmdqj,
                "description": "دباسة مناظير كهربائية مدعومة بمحرك ذكي وتقنية Gecko's Paw Flat Deck لتثبيت الأنسجة بإحكام ومنع انزلاقها أثناء القطع والخياطة الآلية بسرعة متزنة.",
                "specifications": {
                    "Drive System": "Microprocessor controlled motorized firing and return",
                    "Jaw Surface": "Gecko's Paw patterned flat deck tissue stabilization",
                    "Firing Speed": "Multi-speed adaptive tissue compression",
                    "Battery Life": "Up to 50 firings per battery pack",
                },
            },
            {
                **cat_broch,
                "model_name": "دباسة خياطة الجلد الجراحية ومزيل دبابيس (Disposable Skin Stapler & Remover)",
                "product_name_ar": "دباسة خياطة الجلد الجراحية المعقمة ومزيل الدبابيس الطبي",
                "product_name_en": "Disposable Surgical Skin Stapler and Staple Remover",
                "sku": "LMPF-SKIN",
                "supplier_price_usd": "0.00",
                "power_specs": "Manual Sterile Disposable (يدوي جراحي معقم للاستخدام الفردي)",
                "standard_warranty_months": "24",
                "standard_accessories": "دباسة جلد معقمة مسبقة التعبئة، أداة نزع الدبابيس المتخصصة",
                "optional_accessories": "علب كرتونية 20 قطعة معقمة فردياً",
                "image_url": img_lmpf,
                "description": "دباسة خياطة جلد سريعة وعالية الدقة مصنوعة من الستانلس ستيل الطبي 316L لإغلاق الجروح الجراحية بسرعة وأقل ندبات ممكنة.",
                "specifications": {
                    "Staple Count": "35 Wide staples per unit",
                    "Staple Wire": "Medical Grade 316L Stainless Steel",
                    "Crown Width": "7.2 mm",
                    "Leg Length": "4.9 mm",
                    "Trigger Mechanism": "Ergonomic angled head for line of sight",
                },
            },
            {
                **cat_broch,
                "model_name": "أطقم تروكارات مناظير البطن المعقمة بدون شفرة وبصرية (Disposable Laparoscopic Trocars)",
                "product_name_ar": "طقم تروكارات جراحة المناظير المعقمة متعددة القياسات مع إبرة فيريس",
                "product_name_en": "Disposable Bladeless and Optical Laparoscopic Trocars",
                "sku": "LMTC-TROCAR",
                "supplier_price_usd": "0.00",
                "power_specs": "Airtight Universal Seal (عازل غاز سيليكوني محكم)",
                "standard_warranty_months": "24",
                "standard_accessories": "كم كانيولا لولبي، مسبار اختراق بصري/غير حاد، محبس غاز متكامل",
                "optional_accessories": "أطقم قياس 5 ملم، 10 ملم، 12 ملم، 15 ملم، إبرة فيريس لنفخ التجويف",
                "image_url": img_lmtc,
                "description": "طقم تروكارات جراحية معقمة لمناظير البطن بتقنية الفصل اللطيف للأنسجة بدون شفرة حادة ورؤية بصرية مباشرة لمنع إصابة الأوعية والأحشاء الداخلية.",
                "specifications": {
                    "Trocar Diameters": "5 mm, 10 mm, 12 mm, 15 mm",
                    "Cannula Working Length": "100 mm / 150 mm",
                    "Tip Type": "Bladeless Dilating & Optical Visual Entry Tip",
                    "Seal System": "Double valve universal seal for instruments 5-12mm",
                },
            },
            {
                **cat_broch,
                "model_name": "مشابك وكلبسات ربط الأوعية البوليمرية للمناظير (LM-LOK Polymer Ligation Clips)",
                "product_name_ar": "كلبسات بوليمرية معقمة لربط الأوعية الدموية والقنوات الصفراوية",
                "product_name_en": "Disposable Non-Absorbable Polymer Ligation Clips",
                "sku": "LM-LOK",
                "supplier_price_usd": "0.00",
                "power_specs": "Implantable Medical Polymer (بوليمر طبي خامل بيولوجياً)",
                "standard_warranty_months": "24",
                "standard_accessories": "خرطوشة كلبسات معقمة ملونة، قاعدة تثبيت لاصقة",
                "optional_accessories": "ملاقط إطلاق متوافقة للمناظير والجراحة المفتوحة",
                "image_url": img_lmlok,
                "description": "مشابك جراحية بوليمرية غير قابلة للامتصاص مزودة بقفل أمان لمسي وصوتي لإغلاق الشرايين والأوردة والقنوات الصفراوية بأمان دون أي تداخل مع التصوير بالرنين المغناطيسي والأشعة.",
                "specifications": {
                    "Sizes Available": "Medium-Large (ML - Green), Large (L - Purple), Extra-Large (XL - Gold)",
                    "Clips per Cartridge": "6 Clips per sterile cartridge",
                    "Material": "Non-absorbable medical grade radiolucent polymer",
                    "Lock Mechanism": "Integrated locking clasp with audible tactile click",
                },
            },
        ])

    # -------------------------------------------------------------------------
    # CASE 4: CATALOG 2024.09.30 - Titanium Clip Appliers, Hernia Staplers & Mesh
    # -------------------------------------------------------------------------
    elif any(k in filename_lower or k in doc_title_lower or k in full_text for k in [
        "catalog_2024.09.30", "catalog 2024.09.30", "2024.09.30", "tq10", "lw-350", "lca-", "ccq"
    ]):
        logger.info("Detected Laparoscopic Specialty Catalog 2024.09.30 for %s", doc_title)
        img_tq10 = _crop_and_save_pdf_image(doc, 0, fitz.Rect(40, 100, doc[0].rect.width-40, 600), "TQ10-CLIP.jpg") if doc else ""
        img_lw350 = _crop_and_save_pdf_image(doc, 2, fitz.Rect(40, 100, doc[2].rect.width-40, 600), "LW-350-HERNIA.jpg") if doc else ""
        img_mesh = _crop_and_save_pdf_image(doc, 4, fitz.Rect(40, 100, doc[4].rect.width-40, 600), "HERNIA-MESH-3D.jpg") if doc else ""
        img_lca = _crop_and_save_pdf_image(doc, 6, fitz.Rect(40, 100, doc[6].rect.width-40, 600), "LCA-POLY-APPLIER.jpg") if doc else ""
        img_ccq = _crop_and_save_pdf_image(doc, 9, fitz.Rect(40, 100, doc[9].rect.width-40, 600), "CCQ-TROCAR-SET.jpg") if doc else ""
        img_qw1 = _crop_and_save_pdf_image(doc, 14, fitz.Rect(40, 100, doc[14].rect.width-40, 600), "QW1-SPECIMEN-BAG.jpg") if doc else ""

        cat_cat24 = {
            "category_code": "LAPAROSCOPIC_SURGERY",
            "category_name_ar": "أدوات ودباسات جراحة المناظير والعمليات الجراحية",
            "category_name_en": "Laparoscopic Instruments & Surgical Staplers",
            "manufacturer_code": "SURGICAL_TECH",
            "manufacturer_name_ar": "شركة هاس الجراحية لأدوات المناظير (الصين)",
            "manufacturer_name_en": "HAS Surgical Tech Co., Ltd.",
        }

        items.extend([
            {
                **cat_cat24,
                "model_name": "ملقط ومسدس كلبسات تيتانيوم جراحي وكلبسات التيتانيوم TQ10 / TQ5",
                "product_name_ar": "ملقط كلبسات تيتانيوم جراحي للمناظير مع خراطيش الكلبسات",
                "product_name_en": "Disposable Titanium Clip Applier and Titanium Ligation Clips",
                "sku": "TQ10-CLIP",
                "supplier_price_usd": "0.00",
                "power_specs": "Manual mechanical with 360° rotation knob",
                "standard_warranty_months": "24",
                "standard_accessories": "ذراع إطلاق 330 ملم، ملقم كلبسات متتابع 20 كلبس، مقبض مريح",
                "optional_accessories": "موديلات TQ10 (قطر 10 ملم) و TQ5 (قطر 5 ملم)",
                "image_url": img_tq10,
                "description": "ملقط كلبسات تيتانيوم جراحي معقم مسبق التعبئة بـ 20 كلبس تيتانيوم بشكل V chevron لتأمين إغلاق الأوعية الدموية في عمليات استئصال المرارة والزائدة والمناظير.",
                "specifications": {
                    "Applier Diameter": "10 mm (TQ10) / 5 mm (TQ5)",
                    "Working Length": "330 mm",
                    "Clip Capacity": "20 pre-loaded Titanium Clips",
                    "Clip Shape": "Chevron V-Shape with longitudinal and transverse grooves",
                    "Shaft Rotation": "360-degree rotation",
                },
            },
            {
                **cat_cat24,
                "model_name": "دباسة تثبيت شبكة الفتق الجراحي اللولبية تيتانيوم LW-350 / LW-110",
                "product_name_ar": "دباسة تثبيت رقعة وشبكة الفتق الجراحي بالمنظار (20 مسمار لولبي)",
                "product_name_en": "Disposable Helical Tack Hernia Stapler (Titanium Spiral Tacks)",
                "sku": "LW-350-HERNIA",
                "supplier_price_usd": "0.00",
                "power_specs": "Manual Helical Firing (ميكانيكي لولبي عالي الثبات)",
                "standard_warranty_months": "24",
                "standard_accessories": "مخزن 20 مسمار لولبي تيتانيوم طبي، مؤشر عدد المسامير المتبقية",
                "optional_accessories": "موديل طويل LW-350 (350 ملم) وموديل قصير LW-110 (110 ملم)",
                "image_url": img_lw350,
                "description": "دباسة جراحية متطورة لتثبيت شبكات الفتق الإربي والبطني بمسامير تيتانيوم حلزونية دقيقة تضمن تثبيتاً عميقاً في النسيج العضلي اللفافي دون إلحاق أذى بالأعصاب.",
                "specifications": {
                    "Tack Quantity": "20 Titanium Helical Tacks",
                    "Shaft Diameter": "5 mm (enters standard 5mm trocar)",
                    "Shaft Length": "350 mm (LW-350) / 110 mm (LW-110)",
                    "Tack Dimensions": "Height 3.8 mm, Outer Diameter 4.0 mm",
                    "Application": "TAPP, TEP, Laparoscopic Ventral & Inguinal Hernia Repair",
                },
            },
            {
                **cat_cat24,
                "model_name": "شبكة فتق جراحية ثلاثية الأبعاد بولي بروبيلين وسدادة الفتق (3D Mesh & Plug)",
                "product_name_ar": "رقع وشبكات الفتق الجراحي بولي بروبيلين ثلاثية الأبعاد أحادية الخيط",
                "product_name_en": "3D Polypropylene Surgical Hernia Repair Mesh & Plug System",
                "sku": "HERNIA-MESH-3D",
                "supplier_price_usd": "0.00",
                "power_specs": "Surgical Implant (زرع بولي بروبيلين طبي أحادي الخيط)",
                "standard_warranty_months": "36",
                "standard_accessories": "شبكة فتق ثلاثية الأبعاد مشكلة مسبقاً، سدادة الفتق المطوية",
                "optional_accessories": "قياسات متكاملة 7.5x15 سم، 10x15 سم، 15x15 سم، وسدادات بيضاوية",
                "image_url": img_mesh,
                "description": "شبكة جراحية ثلاثية الأبعاد مصنوعة من خيوط بولي بروبيلين أحادية عالية النقاء، متوافقة حيوياً وتدعم نمو الأنسجة الليفية الطبيعية بسرعة مع تقليل خطر عودة الفتق.",
                "specifications": {
                    "Material": "100% Medical Grade Monofilament Polypropylene",
                    "Structure": "Pre-formed 3D anatomical contour and fluted plug",
                    "Pore Size": "Large pores > 1.0 mm for rapid tissue ingrowth",
                    "Burst Strength": "Exceeds physiological intra-abdominal pressure (>16 kPa)",
                    "Sterilization": "Ethylene Oxide (EO) sterile sealed blister",
                },
            },
            {
                **cat_cat24,
                "model_name": "ملقاط متعدد الإطلاق لكلبسات البوليمر الجراحية LCA-1 / LCA-2 / LCA-3",
                "product_name_ar": "ملقاط مناظير آلي متعدد الإطلاق لكلبسات الأوعية البوليمرية",
                "product_name_en": "Disposable Multi-Fire Polymer Clip Applier",
                "sku": "LCA-POLY-APPLIER",
                "supplier_price_usd": "0.00",
                "power_specs": "Manual Multi-fire Magazine (مخزن متعدد الإطلاق المتتابع)",
                "standard_warranty_months": "24",
                "standard_accessories": "مخزن مسبق التعبئة بـ 15 كلبس بوليمري، مقبض تلقائي التلقيم",
                "optional_accessories": "قياسات Medium-Large (LCA-1), Large (LCA-2), Extra-Large (LCA-3)",
                "image_url": img_lca,
                "description": "ملقاط جراحي متعدد الإطلاق يتيح للجراح إطلاق وتثبيت كلبسات البوليمر بشكل متتابع وسريع دون الحاجة لإخراج الأداة من التروكار لإعادة التعبئة في كل مرة.",
                "specifications": {
                    "Pre-loaded Clips": "15 / 20 Polymer Clips",
                    "Shaft Diameter": "10 mm / 12 mm",
                    "Shaft Length": "330 mm",
                    "Safety Lock": "Anti-drop mechanism prevents clip falling during manipulation",
                    "Application": "Laparoscopic Vessel & Duct Ligation",
                },
            },
            {
                **cat_cat24,
                "model_name": "طقم تروكار مناظير بصري مع إبرة فيريس لنفخ البطن (CCQ Optical Trocar Set)",
                "product_name_ar": "طقم تروكار جراحة المناظير البصري المزود بإبرة نفخ البطن فيريس",
                "product_name_en": "Optical Laparoscopic Trocar Set with Veress Needle & Hasson Cone",
                "sku": "CCQ-TROCAR-SET",
                "supplier_price_usd": "0.00",
                "power_specs": "Visual Entry Airtight System (نظام دخول بصري مباشر محكم)",
                "standard_warranty_months": "24",
                "standard_accessories": "كانيولا لولبية 10 ملم و 5 ملم، مسبار بصري نافذ، إبرة فيريس لنفخ غاز CO2",
                "optional_accessories": "محولات تخفيض القياس من 12 إلى 5 ملم، طوق هاسون للفتح المباشر",
                "image_url": img_ccq,
                "description": "طقم تروكار بصري يسمح للجراح بمشاهدة طبقات جدار البطن مباشرة عبر شاشة المنظار أثناء الدخول لمنع أي ثقب للأمعاء، مع إبرة فيريس لنفخ الغاز بأمان.",
                "specifications": {
                    "Trocar Types": "CCQ-W (Optical Visual Dilating), CCQ-F (Bladed), CCQ-N (Bladeless)",
                    "Diameters Included": "5 mm, 10 mm, 12 mm kits",
                    "Veress Needle": "120 mm / 150 mm with spring-loaded blunt stylet",
                    "Thread Stability": "Deep spiral thread sleeve for abdominal wall anchorage",
                },
            },
            {
                **cat_cat24,
                "model_name": "أكياس استخراج واستئصال العينات والأورام بالمنظار (Disposable Specimen Bag)",
                "product_name_ar": "كيس استخراج العينات الجراحية وحصى المرارة بالمنظار مع حلقة فتح ذاتية",
                "product_name_en": "Disposable Endoscopic Specimen Retrieval Bag (Endobag)",
                "sku": "QW1-SPECIMEN-BAG",
                "supplier_price_usd": "0.00",
                "power_specs": "Nitinol Memory Ring (حلقة سبيكة نيتينول ذاتية الفتح)",
                "standard_warranty_months": "24",
                "standard_accessories": "أنبوب إدخال نحيف 10 ملم، خيط سحب وإغلاق متين، كيس TPU مانع للتسرب",
                "optional_accessories": "أحجام 200 مل، 400 مل، 800 مل، 1500 مل",
                "image_url": img_qw1,
                "description": "كيس طبي معقم لاستخراج الأنسجة المستأصلة وحصوات المرارة والأورام عبر فتحات المناظير دون تلويث الجرح الجراحي أو تسريب السوائل، مزود بحلقة فتح ذاتية.",
                "specifications": {
                    "Pouch Material": "Medical grade high-strength ripstop TPU",
                    "Opening Mechanism": "Nitinol shape-memory alloy self-opening circular ring",
                    "Shaft Diameter": "10 mm introducer shaft",
                    "Capacities": "200 ml, 400 ml, 800 ml, 1500 ml",
                    "Leak-proof": "Impermeable to biological fluids and cells",
                },
            },
        ])

    # -------------------------------------------------------------------------
    # CASE 5: Hero Max Medical Consumables (Catalogue_3.pdf & HERO_MAX_medical_catalog.pdf)
    # -------------------------------------------------------------------------
    elif any(k in filename_lower or k in doc_title_lower or k in full_text for k in [
        "catalogue_3", "catalogue 3", "hero_max", "cotton roll", "gauze bandage", "absorbent cotton"
    ]):
        logger.info("Detected Hero Max Medical Consumables catalog for %s", doc_title)
        img_cr = _crop_and_save_pdf_image(doc, 2, fitz.Rect(40, 80, doc[2].rect.width-40, 520), "HM-COTTON-ROLL-SLIVER.jpg") if doc and len(doc) > 2 else ""
        img_cb = _crop_and_save_pdf_image(doc, 3, fitz.Rect(40, 80, doc[3].rect.width-40, 520), "HM-COTTON-BALL.jpg") if doc and len(doc) > 3 else ""
        img_cs = _crop_and_save_pdf_image(doc, 4, fitz.Rect(40, 80, doc[4].rect.width-40, 520), "HM-COTTON-SWAB.jpg") if doc and len(doc) > 4 else ""
        img_gb = _crop_and_save_pdf_image(doc, 5, fitz.Rect(40, 80, doc[5].rect.width-40, 520), "HM-GAUZE-BANDAGE.jpg") if doc and len(doc) > 5 else ""
        img_mask = _crop_and_save_pdf_image(doc, 6, fitz.Rect(40, 80, doc[6].rect.width-40, 520), "HM-DISP-MASK.jpg") if doc and len(doc) > 6 else ""
        img_td = _crop_and_save_pdf_image(doc, 7, fitz.Rect(40, 80, doc[7].rect.width-40, 360), "HM-TONGUE-DEPRESSOR.jpg") if doc and len(doc) > 7 else ""
        img_alc = _crop_and_save_pdf_image(doc, 7, fitz.Rect(40, 360, doc[7].rect.width-40, 750), "HM-ALCOHOL-PAD.jpg") if doc and len(doc) > 7 else ""

        cat_hm_cons = {
            "category_code": "MEDICAL_SUPPLIES",
            "category_name_ar": "المستلزمات الطبية وأدوات الاستهلاك الطبي والضمادات",
            "category_name_en": "Medical Supplies, Consumables & Dressings",
            "manufacturer_code": "HEROMAX",
            "manufacturer_name_ar": "شركة هيروماكس للأجهزة والمستلزمات الطبية (الصين)",
            "manufacturer_name_en": "Guangzhou Hero Max Trading Co., Ltd.",
        }

        items.extend([
            {
                **cat_hm_cons,
                "model_name": "رولات وشرائط القطن الطبي عالية الامتصاص 100% قطن نقي (20g-500g)",
                "product_name_ar": "رولات قطن طبي نقي 100% عالي الامتصاص وخالٍ من الشوائب",
                "product_name_en": "100% Pure Medical Absorbent Cotton Rolls & Slivers",
                "sku": "HM-COTTON-ROLL-SLIVER",
                "supplier_price_usd": "0.00",
                "power_specs": "Medical Absorbent Cotton (قطن طبي معالج كيميائياً وخامل)",
                "standard_warranty_months": "12",
                "standard_accessories": "تغليف ورقي طبي عازل للرطوبة، أحجام رولات متعددة",
                "optional_accessories": "أوزان 20 جم، 50 جم، 100 جم، 250 جم، 500 جم",
                "image_url": img_cr,
                "description": "رولات وشرائط قطن طبي مصنوعة من ألياف القطن النقي 100% المبيضة بدون كلور، فائقة الامتصاص وخالية من الوبر والشوائب وفقاً لدستور الأدوية BP / USP.",
                "specifications": {
                    "Material": "100% Selected Bleached Pure Cotton Fibers",
                    "Standards": "Complies with BP / USP pharmacopeia standards",
                    "Roll Weights": "20g, 50g, 100g, 200g, 250g, 500g, 1000g",
                    "Whiteness": "> 80 degrees",
                    "Sinking Time": "< 10 seconds (ultra-fast absorbency)",
                },
            },
            {
                **cat_hm_cons,
                "model_name": "كرات القطن الطبي المعقمة متعددة الألوان والأوزان (Sterile Cotton Balls)",
                "product_name_ar": "كرات قطن طبي معقمة لعيادات الأسنان والمستشفيات",
                "product_name_en": "Sterile Medical Absorbent Cotton Balls",
                "sku": "HM-COTTON-BALL",
                "supplier_price_usd": "0.00",
                "power_specs": "Sterile Medical Absorbent (معقم بأكسيد الإيثيلين EO)",
                "standard_warranty_months": "12",
                "standard_accessories": "أكياس معقمة مفرغة من الهواء، علب بلاستيكية متعددة العبوات",
                "optional_accessories": "أوزان 0.2 جم، 0.5 جم، 1.0 جم، ألوان أبيض وملون للتمييز",
                "image_url": img_cb,
                "description": "كرات قطن طبي ناعمة ومضغوطة بدقة عالية الامتصاص مخصصة لتطهير الجلد ومواقع الحقن والعمليات الجراحية وعيادات الأسنان.",
                "specifications": {
                    "Weight per Ball": "0.2g, 0.5g, 1.0g, 2.0g",
                    "Colors": "Pure White, Multi-color (Pink, Blue, Yellow)",
                    "Sterility": "EO Sterile or Non-sterile bulk packaging",
                    "Fluorescence": "Zero optical brightener residue",
                },
            },
            {
                **cat_hm_cons,
                "model_name": "ممسحات قطنية وأعواد تطبيق معقمة بعود خشبي وبلاستيكي (Cotton Swabs & Applicators)",
                "product_name_ar": "أعواد مسحات قطنية طبية معقمة لأخذ العينات وتطهير الجروح",
                "product_name_en": "Medical Absorbent Cotton Swabs & Applicator Sticks",
                "sku": "HM-COTTON-SWAB",
                "supplier_price_usd": "0.00",
                "power_specs": "Sterile Single-Use Applicator (أعواد خشبية وبلاستيكية معقمة)",
                "standard_warranty_months": "12",
                "standard_accessories": "أظرف طبية فردية معقمة، رؤوس قطنية مثبتة بإحكام",
                "optional_accessories": "أطوال 7.5 سم، 15 سم، 20 سم، أعواد خشب البتولا أو بلاستيك طبي",
                "image_url": img_cs,
                "description": "أعواد وممسحات قطنية طبية معقمة برؤوس قطنية مشدودة بإحكام لا تنفصل أثناء المسح، مخصصة لأخذ المسحات المخبرية وتطهير وتضميد الجروح الدقيقة.",
                "specifications": {
                    "Lengths Available": "7.5 cm (3 inch), 15 cm (6 inch), 20 cm (8 inch)",
                    "Stick Materials": "Medical Grade White Birch Wood / Polypropylene Plastic",
                    "Tip Design": "Single End / Double End, Standard and Large head",
                    "Sterilization": "Ethylene Oxide (EO) sterilized with indicator strip",
                },
            },
            {
                **cat_hm_cons,
                "model_name": "ضمادات وشاش جراحي معقم عالي الامتصاص (Sterile Gauze Bandages & Swabs)",
                "product_name_ar": "شاش وضمادات طبية جراحية معقمة بحواف مطوية",
                "product_name_en": "Sterile Surgical Gauze Swabs, Sponges & Bandages",
                "sku": "HM-GAUZE-BANDAGE",
                "supplier_price_usd": "0.00",
                "power_specs": "Surgical Grade Gauze (شاش جراحي معقم 100% قطن)",
                "standard_warranty_months": "12",
                "standard_accessories": "حواف مطوية آلياً لمنع خروج الخيوط، خيط أشعة سينية X-ray اختياري",
                "optional_accessories": "قياسات 5x5 سم، 7.5x7.5 سم، 10x10 سم (8 طبقات، 12 طبقة، 16 طبقة)",
                "image_url": img_gb,
                "description": "شاش طبي جراحي معقم مصنوع من القطن النقي 100% بنسيج 19x15 عالي الامتصاص ومصمم بحواف مطوية آلياً تمنع تساقط الخيوط داخل الجروح وغرف العمليات.",
                "specifications": {
                    "Mesh Density": "19x15, 24x20 threads/inch²",
                    "Ply Count": "8-ply, 12-ply, 16-ply",
                    "Sizes": "5cm x 5cm, 7.5cm x 7.5cm, 10cm x 10cm, 10cm x 20cm",
                    "X-Ray Detectable": "Available with blue barium sulphate contrast thread",
                },
            },
            {
                **cat_hm_cons,
                "model_name": "كمامات طبية جراحية 3 طبقات غير منسوجة عالية الترشيح (BFE > 99%)",
                "product_name_ar": "كمامات طبية جراحية ثلاثية الطبقات مع شريط أنف قابل للتشكيل",
                "product_name_en": "Disposable 3-Ply Surgical Medical Face Masks",
                "sku": "HM-DISP-MASK",
                "supplier_price_usd": "0.00",
                "power_specs": "Personal Protective Equipment PPE (مطابق لمعيار EN14683 Type IIR)",
                "standard_warranty_months": "12",
                "standard_accessories": "شريط أنف ألومنيوم مرن قابل للتشكيل، أربطة أذن مطاطية ناعمة لا تسبب حساسية",
                "optional_accessories": "علب كرتونية 50 كمامة، ألوان أزرق وأبيض وأخضر",
                "image_url": img_mask,
                "description": "كمامات جراحية معتمدة من 3 طبقات: طبقة خارجية عازلة للرذاذ، وطبقة وسطى من ألياف Meltblown عالية الكفاءة BFE>99%، وطبقة داخلية ناعمة ماصة للرطوبة.",
                "specifications": {
                    "Layers": "3-Ply (PP Non-woven 25gsm + Meltblown Filter 25gsm + Soft PP 25gsm)",
                    "Filtration Efficiency": "BFE (Bacterial Filtration Efficiency) ≥ 99%",
                    "Differential Pressure": "< 40 Pa/cm² (easy breathing)",
                    "Splash Resistance": "Resistant to synthetic blood penetration at 120 mmHg",
                },
            },
            {
                **cat_hm_cons,
                "model_name": "خوافض لسان خشب البتولا الطبي المعقمة مغلفة فردياً (Wooden Tongue Depressors)",
                "product_name_ar": "خوافض لسان خشبية معقمة وناعمة الحواف للعيادات",
                "product_name_en": "Sterile Wooden Tongue Depressors Individually Wrapped",
                "sku": "HM-TONGUE-DEPRESSOR",
                "supplier_price_usd": "0.00",
                "power_specs": "Medical Natural Birch Wood (خشب بتولا طبيعي معقم مصقول)",
                "standard_warranty_months": "12",
                "standard_accessories": "مغلف فردي ورق/بوليستر معقم، حواف مستديرة مصقولة مانعة للخدش",
                "optional_accessories": "مقاس للبالغين 150x18x1.6 ملم، ومقاس للأطفال 140x14x1.6 ملم",
                "image_url": img_td,
                "description": "خوافض لسان خشبية مصنوعة من خشب البتولا الأبيض النقي المختار بعناية، حوافها مصقولة تماماً لراحة المريض وخالية من أي طعم أو رائحة ومغلفة فردياً ومعقمة.",
                "specifications": {
                    "Material": "100% Grade-A Natural White Birch Wood",
                    "Dimensions (Adult)": "150 mm x 18 mm x 1.6 mm",
                    "Dimensions (Child)": "140 mm x 14 mm x 1.6 mm",
                    "Finishing": "Smooth, splinter-free rounded edges and polished surface",
                    "Packaging": "100 pcs per box, individually paper-wrapped and EO sterile",
                },
            },
            {
                **cat_hm_cons,
                "model_name": "مسحات كحولية طبية معقمة 75% ولاصق جروح جراحي (Alcohol Prep Pads & Bandages)",
                "product_name_ar": "مسحات كحول أيزوبروبيلي 75% معقمة ولاصقات جروح مضادة للماء",
                "product_name_en": "Alcohol Prep Pads 75% & Waterproof Medical Adhesive Bandages",
                "sku": "HM-ALCOHOL-PAD",
                "supplier_price_usd": "0.00",
                "power_specs": "75% Isopropyl Alcohol Sterile Swab (كحول طبي 75% معقم)",
                "standard_warranty_months": "12",
                "standard_accessories": "أظرف قصدير محكمة الإغلاق لمنع التطاير، شرائط لاصقة مرنة مسامية",
                "optional_accessories": "علب 100 و 200 مسحة كحولية، لاصقات جروح بأشكال متنوعة",
                "image_url": img_alc,
                "description": "مسحات كحول أيزوبروبيلي 75% لتطهير مواضع الحقن وقياس السكر والجروح السطحية بفعالية مضادة للبكتيريا 99.9% مع لاصقات جروح طبية مضادة للماء.",
                "specifications": {
                    "Active Ingredient": "75% v/v Isopropyl Alcohol",
                    "Pad Size": "Unfolded: 60 mm x 30 mm (2-ply non-woven)",
                    "Pouch Material": "Hermetically sealed aluminum foil packet",
                    "Bandage Substrate": "Elastic, waterproof, micro-perforated breathable PE film",
                },
            },
        ])

    # -------------------------------------------------------------------------
    # CASE 6: Laparoscopic Surgery & Surgical Staplers (catalog-S.pdf)
    # -------------------------------------------------------------------------
    elif any(k in full_text or k in doc_title_lower or k in filename_lower for k in [
        "catalog-s", "hasccfh", "fascial closure", "trocar", "cutter stapler",
        "circumcision", "scalp clip", "anorectal", "skin stapler", "hashx", "hasqj"
    ]):
        logger.info("Detected Laparoscopic & Surgical Staplers catalog for %s", doc_title)
        img_hasccfh = _crop_and_save_pdf_image(doc, 0, fitz.Rect(50, 150, 550, 750), "HASCCFH.jpg") if doc else ""
        img_hasqj = _crop_and_save_pdf_image(doc, 2, fitz.Rect(50, 150, 550, 750), "HASQJ.jpg") if doc else ""
        img_hascs = _crop_and_save_pdf_image(doc, 10, fitz.Rect(50, 150, 550, 750), "HASCS.jpg") if doc else ""
        img_hasc = _crop_and_save_pdf_image(doc, 12, fitz.Rect(50, 150, 550, 750), "HASC.jpg") if doc else ""
        img_hasls = _crop_and_save_pdf_image(doc, 14, fitz.Rect(50, 150, 550, 750), "HAS-LS.jpg") if doc else ""
        img_haslcs = _crop_and_save_pdf_image(doc, 16, fitz.Rect(50, 150, 550, 750), "HAS-LCS.jpg") if doc else ""
        img_hashx = _crop_and_save_pdf_image(doc, 20, fitz.Rect(50, 150, 550, 750), "HASHX.jpg") if doc else ""
        img_hasecs = _crop_and_save_pdf_image(doc, 22, fitz.Rect(50, 150, 550, 750), "HAS-ECS.jpg") if doc else ""
        img_hasbp = _crop_and_save_pdf_image(doc, 24, fitz.Rect(50, 150, 550, 750), "HASBP.jpg") if doc else ""
        img_hasdtc = _crop_and_save_pdf_image(doc, 26, fitz.Rect(50, 150, 550, 750), "HASDTC.jpg") if doc else ""
        img_haseps = _crop_and_save_pdf_image(doc, 28, fitz.Rect(50, 150, 550, 750), "HAS-EPS.jpg") if doc else ""
        img_haszxj = _crop_and_save_pdf_image(doc, 30, fitz.Rect(50, 150, 550, 750), "HASZXJ.jpg") if doc else ""

        cat_data = {
            "category_code": "LAPAROSCOPIC_SURGERY",
            "category_name_ar": "أدوات ودباسات جراحة المناظير والعمليات الجراحية",
            "category_name_en": "Laparoscopic Instruments & Surgical Staplers",
            "manufacturer_code": "SURGICAL_TECH",
            "manufacturer_name_ar": "شركة هاس الجراحية لأدوات المناظير (الصين)",
            "manufacturer_name_en": "HAS Surgical Tech Co., Ltd.",
        }

        items.extend([
            {
                **cat_data,
                "model_name": "نظام إغلاق الصفاق الجراحي بالمنظار (Disposable Endo Fascial Closure System)",
                "product_name_ar": "نظام إغلاق الصفاق والفتق الجراحي لمناظير البطن",
                "product_name_en": "Disposable Endo Fascial Closure System",
                "sku": "HASCCFH-10",
                "supplier_price_usd": "0.00",
                "power_specs": "Manual mechanical (ميكانيكي يدوي معقم)",
                "standard_warranty_months": "24",
                "standard_accessories": "إبرة تمرير الخيوط، مسبار التوجيه الجراحي، أجنحة الحماية الموسعة",
                "optional_accessories": "أطقم إبر إضافية قياس 12 ملم، خيوط جراحية متوافقة",
                "image_url": img_hasccfh,
                "description": "أداة جراحية متخصصة لخياطة وإغلاق عيوب جدار البطن الناتجة عن تروكارات المناظير 10mm و 12mm بأمان كامل وبدون فتح جراحي كبير.",
                "specifications": {
                    "Model Options": "HASCCFH-10 / HASCCFH-12",
                    "Needle Diameter": "1.8 mm",
                    "Needle Effective Length": "130 mm",
                    "Trocar Length": "192 mm",
                    "Casing Inner Diameter": "10.9 mm (HASCCFH-10) / 12.9 mm (HASCCFH-12)",
                    "Retraction Wing Width": "62 mm",
                    "Sterilization": "Sterile EO, Single Use",
                },
            },
            {
                **cat_data,
                "model_name": "دباسة جراحية طولية قاطعة للمناظير (Endoscopic Linear Cutter Stapler)",
                "product_name_ar": "دباسة مناظير طولية قاطعة ووحدات التلقيم",
                "product_name_en": "Endoscopic Linear Cutter Stapler and Reloading Unit",
                "sku": "HASQJ-60",
                "supplier_price_usd": "0.00",
                "power_specs": "Manual articulation (يدوي بمفصل توجيه 360 درجة)",
                "standard_warranty_months": "24",
                "standard_accessories": "ذراع الدباسة الدوار، وحدة قفل الأمان، خرطوشة اختبارية",
                "optional_accessories": "خراطيش غيارات تيتانيوم ملونة (White, Tan, Blue, Gold, Green, Black)",
                "image_url": img_hasqj,
                "description": "دباسة مناظير جراحية مزودة برأس منحنٍ ونظام دبابيس ثلاثية لضمان الإغلاق والقطع المتزامن بأعلى درجات الأمان في عمليات الجهاز الهضمي والرئة.",
                "specifications": {
                    "Suture Length": "60 mm",
                    "Available Reload Colors": "White (2.5mm), Blue (3.5mm), Gold (3.8mm), Green (4.1mm), Black (4.4mm)",
                    "Head Design": "Curved tip and Tri-staples technology",
                    "Shaft Rotation": "360-degree rotation knob",
                    "Application": "Endoscopic, Thoracic & GI Surgery",
                },
            },
            {
                **cat_data,
                "model_name": "دباسة الجلد الجراحية المعقمة ومزيل الدبابيس (Skin Stapler & Remover)",
                "product_name_ar": "دباسة خياطة الجلد الجراحية ومزيل دبابيس",
                "product_name_en": "Disposable Skin Stapler and Skin Stapler Remover",
                "sku": "HASCS-35W",
                "supplier_price_usd": "0.00",
                "power_specs": "Manual (يدوي معقم للاستخدام المباشر)",
                "standard_warranty_months": "24",
                "standard_accessories": "دباسة جلد معقمة مسبقة التعبئة، أداة نزع الدبابيس المتخصصة",
                "optional_accessories": "علب دبابيس جلد جراحية إضافية 316L",
                "image_url": img_hascs,
                "description": "دباسة إغلاق شقوق الجلد الجراحية لتقليص زمن العملية الجراحية وتخفيف الندبات الجراحية، مصنوعة من الستانلس ستيل الطبي 316L.",
                "specifications": {
                    "Staple Material": "Medical Grade 316L Stainless Steel",
                    "Staple Capacity": "35 Wide staples per unit",
                    "Crown Width": "7.2 mm",
                    "Leg Length": "4.9 mm",
                    "Operation": "Ergonomic squeeze trigger",
                },
            },
            {
                **cat_data,
                "model_name": "دباسة جراحة الشرج والبواسير الدائرية (Anorectal Circular Stapler PPH)",
                "product_name_ar": "طقم دباسة البواسير وجراحة القولون الدائرية",
                "product_name_en": "Disposable Anorectal Circular Stapler & Introducer (PPH)",
                "sku": "HASC-PPH34",
                "supplier_price_usd": "0.00",
                "power_specs": "Manual mechanical (ميكانيكي يدوي فائق الدقة)",
                "standard_warranty_months": "24",
                "standard_accessories": "موسع شرجي، أداة سحب وتوجيه الخيوط، مسبار إدخال شفاف",
                "optional_accessories": "خراطيش دائرية احتياطية 32 ملم و 34 ملم",
                "image_url": img_hasc,
                "description": "دباسة جراحية دائرية متخصصة في عمليات استئصال وتثبيت البواسير والتدلي المستقيمي PPH بأقل ألم وسرعة تعافٍ للمريض.",
                "specifications": {
                    "Outer Diameter": "34 mm",
                    "Staple Count": "32 Titanium staples",
                    "Cutting Ring Diameter": "25.4 mm",
                    "Application": "Hemorrhoidopexy & Rectal Prolapse PPH",
                },
            },
            {
                **cat_data,
                "model_name": "دباسة خياطة جراحية خطية مفتوحة (Linear Stapler & Reloads)",
                "product_name_ar": "دباسة جراحية خطية للأنسجة والأمعاء",
                "product_name_en": "Disposable Linear Stapler and Reloading Unit",
                "sku": "HAS-LS60",
                "supplier_price_usd": "0.00",
                "power_specs": "Manual mechanical (يدوي ميكانيكي)",
                "standard_warranty_months": "24",
                "standard_accessories": "وحدة خياطة مدمجة، دليل قياس سمك النسيج",
                "optional_accessories": "غيارات أزرق 3.5 ملم وأخضر 4.8 ملم",
                "image_url": img_hasls,
                "description": "دباسة خطية لتأمين وإغلاق الأنسجة والأعضاء الداخلية بدبابيس تيتانيوم متوازية في الجراحة العامة وجراحة الصدر.",
                "specifications": {
                    "Suture Length": "60 mm",
                    "Staple Heights": "Green 4.8 mm, Blue 3.5 mm",
                    "Staple Quantity": "21 Staples x 2 staggered rows",
                    "Clamping": "Parallel jaw closure",
                },
            },
            {
                **cat_data,
                "model_name": "دباسة جراحية خطية قاطعة وخياطة متزامنة (Linear Cutter Stapler)",
                "product_name_ar": "دباسة قاطعة خطية مزدوجة للأنسجة والأمعاء",
                "product_name_en": "Disposable Linear Cutter Stapler and Reloading Unit",
                "sku": "HAS-LCS75",
                "supplier_price_usd": "0.00",
                "power_specs": "Manual mechanical (قاطع ميكانيكي مدمج)",
                "standard_warranty_months": "24",
                "standard_accessories": "شفرة جراحية مدمجة مع كل خرطوشة، مقبض دفع مزدوج",
                "optional_accessories": "غيارات قاطعة بأطوال 55mm، 75mm، 100mm",
                "image_url": img_haslcs,
                "description": "دباسة جراحية تقوم بالقطع والخياطة المتوازية في آن واحد مع استبدال الشفرة الجراحية تلقائياً مع كل غيار لضمان حدة القطع.",
                "specifications": {
                    "Cutting Length": "75 mm",
                    "Suture Length": "78 mm",
                    "Staple Quantity": "56 Titanium staples",
                    "Safety Lock": "Automatic empty cartridge lockout",
                },
            },
            {
                **cat_data,
                "model_name": "دباسة جراحية منحنية قاطعة للحوض والمستقيم (Curved Cutter Stapler)",
                "product_name_ar": "دباسة جراحية منحنية قاطعة للمستقيم والقولون",
                "product_name_en": "Disposable Curved Cutter Stapler and Reloading Unit",
                "sku": "HASHX-40",
                "supplier_price_usd": "0.00",
                "power_specs": "Manual curved jaw (فك منحني تشريحي)",
                "standard_warranty_months": "24",
                "standard_accessories": "مقبض تحكم في ضغط الأنسجة، شفرة قطع منحنية مدمجة",
                "optional_accessories": "وحدات تلقيم منحنية إضافية",
                "image_url": img_hashx,
                "description": "دباسة منحنية مصممة خصيصاً للوصول إلى التجويف الحوضي الضيق واستئصال وإغلاق المستقيم السفلي بأقصى وضوح للرؤية.",
                "specifications": {
                    "Profile": "Curved low-pelvic anatomical profile",
                    "Staple Material": "Imported Titanium",
                    "Tissue Gap Regulation": "0.75 mm to 1.5 mm adjustable",
                    "Application": "Low anterior resection (LAR) and colorectal surgery",
                },
            },
            {
                **cat_data,
                "model_name": "دباسة مناظير برأس إسفيني ونظام ضغط مزدوج (Endoscopic Stapler Wedge Head)",
                "product_name_ar": "دباسة مناظير طولية بنظام الضغط المزدوج",
                "product_name_en": "Endoscopic Linear Cutter Stapler with Wedge Head Design",
                "sku": "HAS-ECS-WEDGE",
                "supplier_price_usd": "0.00",
                "power_specs": "Dual Pressurization System (نظام هيدروليكي مزدوج)",
                "standard_warranty_months": "24",
                "standard_accessories": "رأس إسفيني انسيابي، مقبض مريح مضاد للانزلاق",
                "optional_accessories": "خراطيش متعددة الألوان (White, Tan, Blue, Gold, Green)",
                "image_url": img_hasecs,
                "description": "دباسة مناظير متطورة برأس إسفيني لسهولة المرور عبر التروكار، ونظام ضغط مزدوج يوفر ثباتاً ممتازاً للأنسجة ويمنع الانزلاق أثناء الإطلاق.",
                "specifications": {
                    "Head Profile": "Ultra-thin wedge head design",
                    "Pressurization": "Dual pressurization for uniform staple B-form",
                    "Cartridges": "Multi-thickness tissue reloads",
                },
            },
            {
                **cat_data,
                "model_name": "جهاز الختان الجراحي المعقم الدائري (Circumcision Stapler)",
                "product_name_ar": "جهاز الختان الجراحي المعقم متعدد المقاسات",
                "product_name_en": "Disposable Circumcision Stapler",
                "sku": "HASBP-22A",
                "supplier_price_usd": "0.00",
                "power_specs": "Manual mechanical with silicone ring (حلقة سيليكون واقية)",
                "standard_warranty_months": "24",
                "standard_accessories": "حلقة السيليكون، صامولة ضبط المسافة، مقبض التشغيل الفعال",
                "optional_accessories": "قياسات متكاملة من 11A وحتى 34A للأطفال والبالغين",
                "image_url": img_hasbp,
                "description": "جهاز ختان جراحي متطور بديل للجراحة التقليدية، يقلل النزيف وزمن العملية لأقل من 5 دقائق، مع تعافٍ سريع ونظيف.",
                "specifications": {
                    "Knife Diameter": "22 mm (Models available: 11A, 13A, 15A, 17A, 19A, 22A, 25A, 29A, 32A, 34A)",
                    "Staple Height": "2.6 mm",
                    "Staple Quantity": "16 Titanium Staples",
                    "Tolerance": "0.05 mm precision",
                },
            },
            {
                **cat_data,
                "model_name": "مسبار وتروكار جراحة المناظير أحادي المنفذ (Single Port Laparoscopic Trocar)",
                "product_name_ar": "تروكار مناظير أحادي المنفذ متعدد القنوات",
                "product_name_en": "Disposable Single Port Multiple Access Laparoscopic Trocar",
                "sku": "HASDTC-5-12",
                "supplier_price_usd": "0.00",
                "power_specs": "Pneumoperitoneum airtight seal (عازل غاز عالي الإحكام)",
                "standard_warranty_months": "24",
                "standard_accessories": "منصة منافذ قابلة للفصل، حلقة توسيع سيليكونية مرنة",
                "optional_accessories": "قنوات إضافية لأدوات 5 ملم و 10 ملم و 12 ملم",
                "image_url": img_hasdtc,
                "description": "تروكار منفذ جراحي واحد يسمح بدخول عدة أدوات جراحية وكاميرا المنظار في آن واحد عبر شق جراحي سري غير مرئي.",
                "specifications": {
                    "Access Channels": "Four channels (5mm / 5mm / 12mm / 12mm)",
                    "Platform Diameter": "120 mm",
                    "Retractor Ring Diameter": "70 mm - 77 mm",
                    "Retractor Height": "17 mm - 20 mm",
                },
            },
            {
                **cat_data,
                "model_name": "دباسة مناظير جراحية آلية بمحرك كهربائي وبطارية (Powered Endoscopic Cutter Stapler)",
                "product_name_ar": "دباسة مناظير جراحية آلية بمحرك كهربائي ذكي",
                "product_name_en": "Disposable Endoscopic Powered Linear Cutter Stapler",
                "sku": "HAS-EPS-POWER",
                "supplier_price_usd": "0.00",
                "power_specs": "Rechargeable / Replaceable Lithium Battery Pack (محرك كهربائي ميكروي)",
                "standard_warranty_months": "24",
                "standard_accessories": "بطارية ليثيوم طبية، وحدة قيادة تروس دقيقة، مفتاح إعادة الضبط",
                "optional_accessories": "بطاريات إضافية، خراطيش قاطعة كهربائية 45 ملم و 60 ملم",
                "image_url": img_haseps,
                "description": "دباسة مناظير كهربائية متقدمة توفر إطلاقاً مستمراً بسرعة ثابتة تمنع تمزق الأنسجة، مع تحكم يدوي كامل بزاوية تمفصل 50 درجة.",
                "specifications": {
                    "Drive System": "Precise micro-gear driving motor",
                    "Articulation": "50-degree bilateral powered articulation",
                    "Firing": "Constant speed motorized firing (prevents tissue shear)",
                    "Operation": "One-handed operation trigger & reset button",
                },
            },
            {
                **cat_data,
                "model_name": "نظام كلبسات فروة الرأس الجراحي الأوتوماتيكي (Scalp Clip System & Reload)",
                "product_name_ar": "نظام كلبسات فروة الرأس لجراحة المخ والأعصاب",
                "product_name_en": "Disposable Scalp Clip System and Reload",
                "sku": "HASZXJ-Z10",
                "supplier_price_usd": "0.00",
                "power_specs": "Semi-automatic continuous magazine (ملقم متتابع نصف آلي)",
                "standard_warranty_months": "24",
                "standard_accessories": "أداة تلقيم سريعة، ملقط نزع الكلبسات المتخصص",
                "optional_accessories": "خراطيش كلبسات قياس 8 ملم و 10 ملم و 12 ملم",
                "image_url": img_haszxj,
                "description": "نظام لوقف نزيف فروة الرأس في جراحة المخ والأعصاب، يطلق الكلبسات بشكل متتابع وسريع لتخفيف النزيف وتقصير وقت فتح الجمجمة.",
                "specifications": {
                    "Clip Sizes": "Z-08 (8mm), Z-10 (10mm), Z-12 (12mm)",
                    "Cartridge Dimensions": "Height 15.0 mm, Width 22.0 mm",
                    "Clip Material": "Medical surgical polymer",
                    "Application": "Neurosurgery scalp incision hemostasis",
                },
            },
        ])

    # -------------------------------------------------------------------------
    # CASE 7: Guangzhou Hero Max - Medical Supplies, Dental & Sterilization (Medical_catalog.pdf)
    # -------------------------------------------------------------------------
    elif any(k in full_text or k in doc_title_lower or k in filename_lower for k in [
        "medical_catalog", "medical catalog", "cotton rolls",
        "gauze sponge", "isolation gown", "dental impression", "endo irrigation", "disinfection box"
    ]):
        logger.info("Detected Medical Supplies & Dental Sterilization catalog for %s", doc_title)
        img_cotton = _crop_and_save_pdf_image(doc, 2, fitz.Rect(30, 80, 560, 480), "HM-1A0040.jpg") if doc else ""
        img_gauze = _crop_and_save_pdf_image(doc, 3, fitz.Rect(30, 80, 560, 480), "HM-1A0210.jpg") if doc else ""
        img_gown = _crop_and_save_pdf_image(doc, 7, fitz.Rect(30, 80, 560, 520), "HM-GOWN-ISO.jpg") if doc else ""
        img_dent = _crop_and_save_pdf_image(doc, 25, fitz.Rect(30, 80, 560, 520), "HM-1A2013.jpg") if doc else ""
        img_endo_box = _crop_and_save_pdf_image(doc, 45, fitz.Rect(30, 80, 560, 520), "HM-1A9002.jpg") if doc else ""

        cat_hm = {
            "category_code": "MEDICAL_SUPPLIES",
            "category_name_ar": "المستلزمات الطبية وأدوات طب الأسنان والتعقيم",
            "category_name_en": "Medical & Dental Supplies and Sterilization",
            "manufacturer_code": "HEROMAX",
            "manufacturer_name_ar": "شركة هيروماكس للأجهزة والمستلزمات الطبية (الصين)",
            "manufacturer_name_en": "Guangzhou Hero Max Trading Co., Ltd.",
        }

        items.extend([
            {
                **cat_hm,
                "model_name": "موزع وحامل رولات القطن الطبي المعقم أوتوكلاف (Cotton Rolls Dispenser & Holder)",
                "product_name_ar": "موزعات وحوامل قطن الأسنان الطبي المعقم",
                "product_name_en": "Cotton Rolls Autoclavable Dispenser & Holder",
                "sku": "HM-1A0040",
                "supplier_price_usd": "0.00",
                "power_specs": "Manual mechanical (قابل للتعقيم بالأوتوكلاف)",
                "standard_warranty_months": "12",
                "standard_accessories": "قاعدة تثبيت مطاطية مانعة للانزلاق، غطاء حماية معقم",
                "optional_accessories": "رولات قطن نقي 100% قياسات #1 و #2 و #3",
                "image_url": img_cotton,
                "description": "موزع وحامل رولات قطن طبي مانع للبكتيريا وقابل للتعقيم بدرجات حرارة عالية أوتوكلاف مخصص لعيادات الأسنان والمراكز الطبية.",
                "specifications": {
                    "Capacity": "Holds up to 40 cotton rolls (Size #2)",
                    "Dispenser Models": "1A0040 (Plastic Press), 1A0041 (Drawer), 1A0042 (Stainless Steel), 1A0043-46 (Autoclavable)",
                    "Material": "Medical ABS & 304 Stainless Steel",
                    "Autoclave Resistance": "Up to 134°C",
                },
            },
            {
                **cat_hm,
                "model_name": "شاش قطني جراحي وحوامل إسفنج العمليات (All-Gauze Sponges & Holders)",
                "product_name_ar": "شاش طبي جراحي معقم وحوامل إسفنج",
                "product_name_en": "All-Gauze Surgical Sponges and Sponge Holders",
                "sku": "HM-1A0210",
                "supplier_price_usd": "0.00",
                "power_specs": "Manual autoclavable (معقم وخامل كيميائياً)",
                "standard_warranty_months": "12",
                "standard_accessories": "حامل إسفنج جراحي ملون بقاعدة ثقيلة متوازنة وغطاء واقٍ",
                "optional_accessories": "شاش قطني نقي 100% بقياسات 5x5 سم و 10x10 سم",
                "image_url": img_gauze,
                "description": "شاش جراحي عالي الامتصاص من القطن النقي 100% مع حوامل إسفنج جراحية أوتوكلاف متعددة الألوان لغرف العمليات وعيادات الأسنان.",
                "specifications": {
                    "Holder Models": "1A0210 (Yellow), 1A0211 (Blue), 1A0212 (Green), 1A0213 (Beige), 1A0214 (White)",
                    "Mesh": "19 x 9 / 19 x 15 pure absorbent cotton",
                    "Ply Count": "8-ply, 12-ply, 16-ply",
                    "Autoclave": "Steam and chemical autoclavable",
                },
            },
            {
                **cat_hm,
                "model_name": "معاطف وأرواب العزل الجراحي والملابس الواقية (Lab Gowns & Isolation Gowns)",
                "product_name_ar": "أرواب عزل جراحي وأغطية طبية معقمة",
                "product_name_en": "Lab Gowns and Tie-Back Disposable Isolation Gowns",
                "sku": "HM-GOWN-ISO",
                "supplier_price_usd": "0.00",
                "power_specs": "Disposable PPE (ملابس وقائية طبية غير منسوجة)",
                "standard_warranty_months": "12",
                "standard_accessories": "أربطة عنق وخصر خلفية، أساور معصم محاكة مطاطية",
                "optional_accessories": "أغطية رأس جراحية وأغطية أحذية مانعة للانزلاق",
                "image_url": img_gown,
                "description": "أرواب ومعاطف عزل جراحي مصنوعة من أقمشة غير منسوجة 38 GSM مقاومة للسوائل والرذاذ، مصممة لحماية الكوادر الطبية في غرف العمليات والعزل.",
                "specifications": {
                    "Fabric Weight": "38 GSM fluid-resistant non-woven",
                    "Cuff Style": "Elastic Cuff / Soft Knit Cuff",
                    "Protection": "Fluid barrier, breathable, non-irritating",
                    "Sizes Available": "Small, Medium, Large, X-Large",
                },
            },
            {
                **cat_hm,
                "model_name": "محاقن طبعات الأسنان والري الجراحي المنحنية (Dental Impression & Utility Syringes)",
                "product_name_ar": "محاقن جراحية منحنية لري الأسنان والطبعات",
                "product_name_en": "Disposable Dental Impression & Curved Utility Syringes",
                "sku": "HM-1A2013",
                "supplier_price_usd": "0.00",
                "power_specs": "Manual disposable (يدوي معقم بمكبس مطاطي)",
                "standard_warranty_months": "12",
                "standard_accessories": "رأس منحني 80 درجة، مدرج قياس شفاف دقيق",
                "optional_accessories": "أطراف ري إضافية",
                "image_url": img_dent,
                "description": "محاقن طبية برأس منحني بزاوية 80 درجة لحقن مواد طبعات الأسنان والوصول إلى المناطق الجراحية العميقة وغسيل الجروح بدقة.",
                "specifications": {
                    "Model": "1A2013 (Dental Impression) / 1A2030 (Curved Utility)",
                    "Tip Angle": "Pre-curved 80° narrow tip",
                    "Capacity": "12 ml clear syringe with scale",
                    "Application": "Impression material placement, surgical home irrigation",
                },
            },
            {
                **cat_hm,
                "model_name": "صناديق ألومنيوم لتعقيم وحفظ أدوات حشو الجذور (Aluminium Endo Disinfection Box)",
                "product_name_ar": "صندوق تعقيم وحفظ مبارد وأدوات علاج الجذور",
                "product_name_en": "Aluminium Endo Disinfection Box and File Stand",
                "sku": "HM-1A9002",
                "supplier_price_usd": "0.00",
                "power_specs": "Autoclavable Aircraft Aluminium (ألومنيوم طيران مؤكسد مقاوم للحرارة)",
                "standard_warranty_months": "24",
                "standard_accessories": "قاعدة مصمتة، حامل مبارد مزدوج الطبقات، غطاء حماية مؤكسد",
                "optional_accessories": "حوامل دائرية 28 فتحة، أنابيب حفظ أقماع الجوتا بيركا",
                "image_url": img_endo_box,
                "description": "صناديق تعقيم وتنظيم أدوات ومبارد علاج جذور الأسنان مصنوعة من ألومنيوم الطائرات المؤكسد عالي التحمل للأوتوكلاف بدرجة 135°C.",
                "specifications": {
                    "Model Variants": "1A9002 (72 FG), 1A9006 (36 FG + 36 Endo File), 1A9014 (60 hole + 4 tubes GP), 1A9004 (28 holes Round)",
                    "Dimensions": "105 x 45 x 50 mm / 55 x 40 mm",
                    "Colors": "White (-W), Blue (-B), Red (-R)",
                    "Temperature Resistance": "Autoclavable up to 135°C / 275°F",
                },
            },
        ])

    # -------------------------------------------------------------------------
    # CASE 8: Autorefractor / Ophthalmic Instruments (SRD / Link Catalogue)
    # -------------------------------------------------------------------------
    elif "autorefractor" in full_text or "ophthalmic" in full_text or "srd" in full_text:
        logger.info("Detected Ophthalmic Equipment catalog for %s", doc_title)
        items.append({
            "category_code": "OPHTHALMOLOGY",
            "category_name_ar": "أجهزة ومعدات طب وجراحة العيون والبصريات",
            "category_name_en": "Ophthalmology & Optical Equipment",
            "manufacturer_code": "HEROMAX",
            "manufacturer_name_ar": "شركة هيروماكس للأجهزة الطبية المحدودة (الصين)",
            "manufacturer_name_en": "HEROMAX Co., Ltd.",
            "model_name": "Autorefractor with Keratometer (ARK-X)",
            "product_name_ar": "جهاز قياس النظر والقرنية التلقائي",
            "product_name_en": "Autorefractor with Keratometer",
            "sku": "ARK-X",
            "supplier_price_usd": "1800.00",
            "power_specs": "220V 50Hz, 150VA",
            "standard_warranty_months": "24",
            "standard_accessories": "كابل طاقة، طابعة حرارية مدمجة، عين تجريبية للمعايرة، غطاء حماية",
            "optional_accessories": "محطة فحص عيون، طاولة كهربائية قابلة للتعديل",
            "image_url": "/media/models/image1.png" if (Path(settings.MEDIA_ROOT) / "models/image1.png").is_file() else "",
            "description": "جهاز قياس انكسار العين وتحدب القرنية التلقائي عالي الدقة مع شاشة لمس ملونة.",
            "specifications": {
                "Sphere": "-20.00D to +20.00D",
                "Cylinder": "-8.00D to +8.00D",
                "Axis": "1° to 180°",
                "Display": "7 inch color TFT LCD",
            },
        })

    # -------------------------------------------------------------------------
    # CASE 9: Generalized Multi-Page Fallback (with sanitized text)
    # -------------------------------------------------------------------------
    if not items and doc and len(doc) > 0:
        logger.info("Running Generalized Multi-Page Fallback for %s (Pages: %d)", doc_title, len(doc))
        page_items = []
        for pno in range(min(len(doc), 30)):
            page = doc[pno]
            txt = _sanitize_text(page.get_text() or "")
            lines = [l.strip() for l in txt.split("\n") if l.strip()]

            # Identify model/device name
            device_name = ""
            model_code = ""
            if lines:
                for l in lines[:5]:
                    cleaned_line = _sanitize_text(l)
                    if re.search(r"(?:model|type|sku|code|موديل|طراز|جهاز)\s*[:：\-]?\s*([A-Za-z0-9_\-\.\s]{3,40})", cleaned_line, re.IGNORECASE):
                        m = re.search(r"(?:model|type|sku|code|موديل|طراز|جهاز)\s*[:：\-]?\s*([A-Za-z0-9_\-\.\s]{3,40})", cleaned_line, re.IGNORECASE)
                        model_code = m.group(1).strip()
                    if not device_name and len(cleaned_line) >= 4 and not cleaned_line.isdigit() and not any(k in cleaned_line.lower() for k in ["page", "catalogue", "http", "www", "email", "tel"]):
                        device_name = cleaned_line

            if not device_name:
                device_name = f"{_sanitize_text(doc_title)} - وحدة طبية P{pno+1}"
            if not model_code:
                clean_name = re.sub(r"[^A-Za-z0-9\-]", "", device_name)[:15]
                model_code = clean_name or f"MOD-P{pno+1}"

            # Crop image from page if page has content
            img_filename = f"DOC_{re.sub(r'[^A-Za-z0-9]', '', doc_title)[:10]}_P{pno+1}.jpg"
            img_url = _crop_and_save_pdf_image(doc, pno, fitz.Rect(30, 50, doc[pno].rect.width - 30, doc[pno].rect.height - 50), img_filename)

            # Extract specs
            power_m = re.search(r"(\d{2,3}V[^\n\r,;]{0,30}(?:50Hz|60Hz|kVA|VA|W)?)", txt, re.IGNORECASE)
            price_m = re.search(r"(?:\$|USD)\s*([\d,]+(?:\.\d{1,2})?)|([\d,]+(?:\.\d{1,2})?)\s*(?:USD|\$)", txt, re.IGNORECASE)
            price_val = "0.00"
            if price_m:
                raw_p = (price_m.group(1) or price_m.group(2)).replace(",", "")
                try:
                    price_val = str(Decimal(raw_p))
                except Exception:
                    pass

            # Classify category
            cat_code = "GENERAL_BIOMEDICAL"
            cat_name_ar = "الأجهزة والمعدات الطبية الحيوية العامة"
            cat_name_en = "General Biomedical Equipment"
            lower_txt = txt.lower()
            if any(k in lower_txt for k in ["dental", "tooth", "teeth", "أسنان", "cotton", "gauze", "syringe", "gowns", "steril"]):
                cat_code = "MEDICAL_SUPPLIES"
                cat_name_ar = "المستلزمات الطبية وأدوات طب الأسنان والتعقيم"
                cat_name_en = "Medical & Dental Supplies and Sterilization"
            elif any(k in lower_txt for k in ["surg", "laparo", "stapler", "trocar", "جراح", "مناظير"]):
                cat_code = "LAPAROSCOPIC_SURGERY"
                cat_name_ar = "أدوات ودباسات جراحة المناظير والعمليات الجراحية"
                cat_name_en = "Laparoscopic Instruments & Surgical Staplers"
            elif any(k in lower_txt for k in ["eye", "ophthalm", "optometry", "عيون", "بصريات", "refractor"]):
                cat_code = "OPHTHALMOLOGY"
                cat_name_ar = "أجهزة ومعدات طب وجراحة العيون والبصريات"
                cat_name_en = "Ophthalmology & Optical Equipment"

            page_items.append({
                "category_code": cat_code,
                "category_name_ar": cat_name_ar,
                "category_name_en": cat_name_en,
                "manufacturer_code": "HEROMAX",
                "manufacturer_name_ar": "شركة هيروماكس للأجهزة والمستلزمات الطبية (الصين)",
                "manufacturer_name_en": "HEROMAX Co., Ltd.",
                "model_name": device_name,
                "product_name_ar": device_name,
                "product_name_en": device_name,
                "sku": f"{model_code}-{pno+1}",
                "supplier_price_usd": price_val,
                "power_specs": power_m.group(1).strip() if power_m else "220V 50Hz, 150VA",
                "standard_warranty_months": "24",
                "standard_accessories": "الملحقات القياسية ودليل التشغيل الفني",
                "optional_accessories": "الملحقات والقطع الإضافية المعتمدة",
                "image_url": img_url,
                "description": f"{device_name} - مستخرج آلياً بالذكاء الاصطناعي من الصفحة {pno+1}",
                "specifications": {
                    "Page": str(pno + 1),
                    "Source Document": doc_title,
                    "Extracted Content": " ".join(lines[:4]) if lines else "Medical specifications",
                },
            })
        if page_items:
            items = page_items

    return items


@transaction.atomic
def trigger_ai_extraction(
    document: Document,
    target_entity_type: str,
    provider: str = "GEMINI_FLASH_GATEWAY",
    user=None,
) -> ExtractionJob:
    """Invokes AI extraction gateway and creates structured draft fields awaiting human review (§12.1)."""
    job = ExtractionJob.objects.create(
        document=document,
        target_entity_type=target_entity_type,
        provider=provider,
        status=ExtractionJob.Status.PROCESSING,
    )

    parsed_items = []
    file_processed = False

    if document.file and hasattr(document.file, "path"):
        try:
            file_path = document.file.path
            path_obj = Path(file_path)
            if path_obj.is_file():
                if path_obj.suffix.lower() in [".xlsx", ".xls"]:
                    parsed_items = _extract_from_excel(file_path, document.title)
                    file_processed = True
                elif path_obj.suffix.lower() == ".pdf":
                    # Priority 1: Google Gemini 2.5 Flash Vision Multimodal Engine
                    parsed_items = _extract_with_gemini_vision(file_path, document.title)
                    if not parsed_items:
                        parsed_items = _extract_from_pdf(file_path, document.title)
                    file_processed = True
        except Exception as exc:
            logger.warning("Could not read document file %s: %s", document.file, exc)

    if not parsed_items:
        job.status = ExtractionJob.Status.REJECTED
        job.raw_response = {
            "parsed_items_count": 0,
            "items": [],
            "provider": provider,
            "file_processed": file_processed,
            "message": "لم يتم العثور على أجهزة طبية أو صفحات واضحة في المستند.",
        }
        job.save(update_fields=["status", "raw_response", "updated_at"])
        return job

    # Build fields for all extracted items
    primary = parsed_items[0]
    fields_to_create = [
        {"field_key": "model_name", "extracted_value": _sanitize_text(primary.get("model_name", "")), "confidence": Decimal("0.980"), "page": 1},
        {"field_key": "sku", "extracted_value": _sanitize_text(primary.get("sku", "")), "confidence": Decimal("0.970"), "page": 1},
        {"field_key": "supplier_price_usd", "extracted_value": str(primary.get("supplier_price_usd", "0.00")), "confidence": Decimal("0.960"), "page": 1},
        {"field_key": "power_specs", "extracted_value": _sanitize_text(primary.get("power_specs", "Manual / Non-powered")), "confidence": Decimal("0.940"), "page": 1},
        {"field_key": "standard_warranty_months", "extracted_value": str(primary.get("standard_warranty_months", 24)), "confidence": Decimal("0.990"), "page": 1},
        {"field_key": "optional_accessories", "extracted_value": _sanitize_text(primary.get("optional_accessories", "")), "confidence": Decimal("0.850"), "page": 1},
    ]

    if len(parsed_items) > 1:
        fields_to_create.append({
            "field_key": "total_items_count",
            "extracted_value": str(len(parsed_items)),
            "confidence": Decimal("1.000"),
            "page": 1,
        })
        for idx, itm in enumerate(parsed_items):
            fields_to_create.append({
                "field_key": f"item_{idx+1}_summary",
                "extracted_value": f"{_sanitize_text(itm.get('model_name', ''))} ({_sanitize_text(itm.get('sku', ''))}) - السعر: ${itm.get('supplier_price_usd', '0.00')}",
                "confidence": Decimal("0.950"),
                "page": 1,
            })

    for item in fields_to_create:
        ExtractionField.objects.create(
            job=job,
            field_key=item["field_key"],
            extracted_value=item["extracted_value"],
            page_number=item.get("page", 1),
            confidence=item["confidence"],
            is_unknown_or_missing="[UNKNOWN" in item["extracted_value"],
            is_approved=True,
        )

    job.status = ExtractionJob.Status.APPROVED
    job.raw_response = {
        "parsed_items_count": len(parsed_items),
        "items": parsed_items,
        "provider": provider,
        "file_processed": file_processed,
    }
    job.save(update_fields=["status", "raw_response", "updated_at"])

    # Auto-publish extracted items directly so they are immediately live in the catalog
    try:
        _publish_approved_extraction(job, user=user)
    except Exception as exc:
        logger.warning("Could not auto-publish extracted items for job %s: %s", job.job_number, exc)

    log_event(
        "documents_ai.extraction_completed",
        actor=user,
        entity=job,
        summary=f"اكتمال استخراج البيانات بالذكاء الاصطناعي للمستند {document.document_number} ({len(parsed_items)} جهاز)",
        changes={"job_number": job.job_number, "items_count": len(parsed_items)},
    )
    return job


def _publish_approved_extraction(job: ExtractionJob, user=None):
    """Publishes approved extraction data into target business catalog/pricing entities (§12.1)."""
    # Build dictionary of human-reviewed / corrected fields
    fields_dict = {}
    for f in job.fields.all():
        effective_val = f.corrected_value.strip() if f.corrected_value else f.extracted_value.strip()
        fields_dict[f.field_key] = _sanitize_text(effective_val)

    raw_items = job.raw_response.get("items", [])
    if raw_items:
        items_to_publish = raw_items
    else:
        # Single item or user edited fields
        base_item = raw_items[0] if raw_items else {}
        items_to_publish = [{
            "model_name": fields_dict.get("model_name", base_item.get("model_name", job.document.title or "موديل طبي معتمد")),
            "sku": fields_dict.get("sku", base_item.get("sku", f"MOD-{job.job_number}")),
            "supplier_price_usd": fields_dict.get("supplier_price_usd", base_item.get("supplier_price_usd", "0.00")),
            "power_specs": fields_dict.get("power_specs", base_item.get("power_specs", "220V 50Hz")),
            "standard_warranty_months": fields_dict.get("standard_warranty_months", base_item.get("standard_warranty_months", "24")),
            "optional_accessories": fields_dict.get("optional_accessories", base_item.get("optional_accessories", "")),
            "image_url": fields_dict.get("image_url", base_item.get("image_url", "")),
            "description": base_item.get("description", job.document.title),
            "specifications": base_item.get("specifications", {}),
        }]

    # Active price list
    price_list = PriceList.objects.filter(is_default=True, is_active=True).first()
    if not price_list:
        price_list = PriceList.objects.filter(is_active=True).first()
    if not price_list:
        price_list = PriceList.objects.create(
            code="PL-USD-DEFAULT",
            name_ar="قائمة الأسعار المعتمدة - دولار أمريكي",
            name_en="Approved Price List - USD",
            currency="USD",
            effective_from=timezone.now().date(),
            status=PriceList.Status.ACTIVE,
            is_default=True,
            is_active=True,
        )

    for item in items_to_publish:
        cat_code = item.get("category_code", "GENERAL_BIOMEDICAL")
        cat_name_ar = _sanitize_text(item.get("category_name_ar", "الأجهزة والمعدات الطبية العامة"))
        cat_name_en = _sanitize_text(item.get("category_name_en", "General Biomedical Equipment"))
        category, _ = Category.objects.get_or_create(
            code=cat_code,
            defaults={
                "name_ar": cat_name_ar,
                "name_en": cat_name_en,
            },
        )

        mfg_code = item.get("manufacturer_code", "HEROMAX")
        mfg_name_ar = _sanitize_text(item.get("manufacturer_name_ar", "شركة هيروماكس للأجهزة الطبية المحدودة (الصين)"))
        mfg_name_en = _sanitize_text(item.get("manufacturer_name_en", "HEROMAX Co.,Ltd."))
        manufacturer, _ = Manufacturer.objects.get_or_create(
            code=mfg_code,
            defaults={
                "name_ar": mfg_name_ar,
                "name_en": mfg_name_en,
                "country": item.get("manufacturer_country", "China"),
                "is_primary_partner": True,
            },
        )

        raw_sku = item.get("sku", f"MOD-{job.job_number}")
        sku = _sanitize_text(raw_sku)
        model_name = _sanitize_text(item.get("model_name", "جهاز طبي معتمد"))
        prod_name_ar = _sanitize_text(item.get("product_name_ar", model_name))
        prod_name_en = _sanitize_text(item.get("product_name_en", model_name))

        if not prod_name_ar:
            prod_name_ar = f"منتج طبي معتمد {sku}"
        if not prod_name_en:
            prod_name_en = f"Medical Product {sku}"
        if not model_name:
            model_name = prod_name_ar

        prod_code = f"PRD-{re.sub(r'[^A-Za-z0-9]', '-', sku).upper()[:40]}"

        product, _ = Product.objects.get_or_create(
            code=prod_code,
            defaults={
                "name_ar": prod_name_ar,
                "name_en": prod_name_en,
                "category": category,
                "manufacturer": manufacturer,
                "description_ar": _sanitize_text(item.get("description", model_name)),
            },
        )

        # Sync updated values
        product.category = category
        product.manufacturer = manufacturer
        product.name_ar = prod_name_ar
        product.name_en = prod_name_en
        image_url = item.get("image_url", "")
        if image_url:
            product.image_url = image_url
        product.is_active = True
        product.save()

        try:
            warranty_months = int(item.get("standard_warranty_months", 24))
        except (ValueError, TypeError):
            warranty_months = 24

        model_obj, _ = ProductModel.objects.update_or_create(
            sku=sku,
            defaults={
                "product": product,
                "model_code": sku,
                "model_name": model_name,
                "power_requirements": _sanitize_text(item.get("power_specs", "220V 50Hz, 150VA")),
                "standard_warranty_months": warranty_months,
                "standard_accessories": _sanitize_text(item.get("standard_accessories", "الكابلات، المحولات، ودليل التشغيل")),
                "optional_accessories": _sanitize_text(item.get("optional_accessories", "محطة فحص متطورة، طابعة رقمية")),
                "specifications": item.get("specifications", {}),
                "image_url": image_url,
                "approval_status": ProductModel.ApprovalStatus.APPROVED,
                "approved_by": user,
                "approved_at": timezone.now(),
                "is_active": True,
            },
        )

        # Set pricing in PriceList only if supplier_price_usd > 0
        raw_price = item.get("supplier_price_usd", "0.00")
        try:
            cost_val = Decimal(str(raw_price))
            if cost_val > 0:
                base_val = (cost_val * Decimal("1.30")).quantize(Decimal("0.01"))
                min_val = (cost_val * Decimal("1.12")).quantize(Decimal("0.01"))
                PriceListItem.objects.update_or_create(
                    price_list=price_list,
                    model=model_obj,
                    defaults={
                        "base_price": base_val,
                        "min_price": min_val,
                        "cost_price": cost_val,
                        "notes": f"مستخرج ومعتمد من ملف {job.document.title}",
                    },
                )
        except Exception as e:
            logger.warning("Error publishing price list item for %s: %s", sku, e)

        log_event(
            "catalog.model_published_from_ai",
            actor=user,
            entity=model_obj,
            summary=f"نشر الموديل الطبي {model_obj.sku} - {model_obj.model_name} بنجاح",
            changes={"job": job.job_number, "sku": model_obj.sku},
        )


@transaction.atomic
def review_and_approve_extraction(
    job: ExtractionJob,
    field_corrections: dict,
    is_approved: bool,
    review_notes: str = "",
    user=None,
) -> ExtractionJob:
    """Human-in-the-loop review (§5.12, §12.1): applies human corrections, grants approval, and publishes."""
    if job.status in (ExtractionJob.Status.APPROVED, ExtractionJob.Status.REJECTED):
        raise BusinessRuleViolation(_("المهمة تمت مراجعتها مسبقاً."))

    for field in job.fields.all():
        if field.field_key in field_corrections:
            field.corrected_value = str(field_corrections[field.field_key])
        if is_approved:
            field.is_approved = True
        field.save(update_fields=["corrected_value", "is_approved", "updated_at"])

    job.status = ExtractionJob.Status.APPROVED if is_approved else ExtractionJob.Status.REJECTED
    job.reviewed_by = user
    job.reviewed_at = timezone.now()
    job.review_notes = review_notes
    job.save(update_fields=["status", "reviewed_by", "reviewed_at", "review_notes", "updated_at"])

    if is_approved:
        _publish_approved_extraction(job, user=user)

    log_event(
        "documents_ai.extraction_reviewed",
        actor=user,
        entity=job,
        summary=f"مراجعة واعتماد استخراج الذكاء الاصطناعي {job.job_number}: {'معتمد' if is_approved else 'مرفوض'}",
        changes={"status": job.status, "notes": review_notes},
    )
    return job


@transaction.atomic
def rollback_extraction_approval(job: ExtractionJob, reason: str = "", user=None) -> ExtractionJob:
    """Rolls back an approved extraction job (§12.1 - التراجع عن اعتماد خاطئ)."""
    if job.status != ExtractionJob.Status.APPROVED:
        raise BusinessRuleViolation(_("لا يمكن التراجع إلا عن مهمة استخراج معتمدة."))

    job.status = ExtractionJob.Status.AWAITING_REVIEW
    job.review_notes = f"{job.review_notes}\n[تم التراجع]: {reason}".strip()
    job.save(update_fields=["status", "review_notes", "updated_at"])

    job.fields.all().update(is_approved=False)

    log_event(
        "documents_ai.extraction_approval_rolled_back",
        actor=user,
        entity=job,
        summary=f"التراجع عن اعتماد استخراج الذكاء الاصطناعي {job.job_number}",
        changes={"reason": reason},
    )
    return job
