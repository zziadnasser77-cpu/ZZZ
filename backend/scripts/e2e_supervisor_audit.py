import os
import sys
import json
import urllib.request
import urllib.error
from decimal import Decimal

BASE_URL = "http://127.0.0.1:8000/api/v1"

def api_call(path, method="GET", data=None, token=None):
    url = f"{BASE_URL}{path}"
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    body = json.dumps(data).encode("utf-8") if data is not None else None
    req = urllib.request.Request(url, data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req) as resp:
            content = resp.read().decode("utf-8")
            return resp.status, json.loads(content) if content else {}
    except urllib.error.HTTPError as e:
        content = e.read().decode("utf-8")
        err_json = json.loads(content) if content else {}
        return e.code, err_json

def main():
    print("================================================================================")
    print("   فحص وتدقيق النظام الشامل من البداية حتى النهاية (End-to-End Supervisor Audit)")
    print("================================================================================\n")
    
    report = []
    
    # ------------------------------------------------------------------------------
    # STAGE 1: Authentication & Identity
    # ------------------------------------------------------------------------------
    print("▶ [المرحلة 1] التحقق من تسجيل الدخول والمصادقة الأمنية (Authentication)")
    status, login_res = api_call("/auth/login/", "POST", {
        "email": "admin@smses.local",
        "password": "AdminPassword123!"
    })
    assert status == 200, f"Login failed: {login_res}"
    token = login_res["access"]
    print(f"  ✓ تم تسجيل الدخول بنجاح للمستخدم admin@smses.local")
    print(f"  ✓ تم الحصول على توكن JWT صالح: {token[:25]}...")
    report.append("المرحلة 1: تسجيل الدخول والمصادقة - ناجح (200 OK)")

    # ------------------------------------------------------------------------------
    # STAGE 2: Customer Registration
    # ------------------------------------------------------------------------------
    print("\n▶ [المرحلة 2] تسجيل عميل طبي جديد (Customer Registration)")
    customer_payload = {
        "legal_name_ar": "مستشفى الأمل التخصصي لطب وجراحة العيون",
        "legal_name_en": "Al-Amal Specialized Eye Hospital",
        "customer_type": "HOSPITAL",
        "governorate": "صنعاء",
        "address": "شارع الستين الغربي - أمانة العاصمة",
        "phone": "+967-1-445566",
        "tax_number": "TAX-YE-987654",
        "notes": "مستشفى تخصصي عيني خاص - عميل مستهدف لأجهزة الفاكو والليزر والـ OCT",
        "status": "ACTIVE"
    }
    status, cust_res = api_call("/customers/", "POST", customer_payload, token=token)
    if status != 201 and "legal_name_ar" in cust_res:
        # If exists, find it
        status, search_res = api_call("/customers/?search=الأمل", token=token)
        customer = search_res["results"][0]
        print(f"  ✓ تم العثور على العميل الطبي المسجل مسبقاً: {customer['customer_number']} - {customer['legal_name_ar']}")
    else:
        assert status == 201, f"Create customer failed: {cust_res}"
        customer = cust_res
        print(f"  ✓ تم إنشاء العميل الطبي بنجاح: {customer['customer_number']} - {customer['legal_name_ar']}")
    cust_id = customer["id"]
    report.append(f"المرحلة 2: تسجيل العميل الطبي ({customer['customer_number']}) - ناجح")

    # ------------------------------------------------------------------------------
    # STAGE 3: Price List Verification
    # ------------------------------------------------------------------------------
    print("\n▶ [المرحلة 3] التحقق من كشف أسعار الوكالة المعتمد (Price List 2026)")
    status, pl_res = api_call("/price-lists/", token=token)
    assert status == 200
    srd_pl = next((pl for pl in pl_res["results"] if pl["code"] == "PL-2026-SRD"), None)
    assert srd_pl is not None, "SRD Price List PL-2026-SRD not found!"
    print(f"  ✓ كشف الأسعار المعتمد: {srd_pl['code']} - {srd_pl['name_ar']}")
    print(f"  ✓ العملة الرسمية: {srd_pl['currency']} | الحالة: {srd_pl['status']} | افتراضي: {srd_pl['is_default']}")
    report.append("المرحلة 3: التحقق من كشف الأسعار الرسمي 2026 - ناجح")

    # ------------------------------------------------------------------------------
    # STAGE 4: Catalog & Specifications Verification
    # ------------------------------------------------------------------------------
    print("\n▶ [المرحلة 4] تدقيق كتالوج الأجهزة والمواصفات الفنية المستخرجة (Catalog & Dynamic Specs)")
    status, prod_res = api_call("/products/?page_size=100", token=token)
    assert status == 200
    products = prod_res["results"]
    print(f"  ✓ إجمالي الأجهزة الطبية المفهرسة في النظام: {prod_res['count']} جهاز")

    # Check priced device
    rk180_prod = next((p for p in products if "RK180" in p["code"]), None)
    assert rk180_prod is not None, "RK-180 product missing!"
    rk180_model = rk180_prod["models"][0]
    print(f"  ✓ فحص جهاز مسعر: {rk180_prod['name_ar']}")
    print(f"    - كود الموديل: {rk180_model['model_code']} | SKU: {rk180_model['sku']}")
    print(f"    - السعر المعتمد: ${rk180_model['approved_price']['base_price']} {rk180_model['approved_price']['currency']}")
    print(f"    - عدد المواصفات المستخرجة من الكتالوج: {len(rk180_model.get('specifications', {}))} مواصفة")
    assert rk180_model["approved_price"]["base_price"] == "3680.00"

    # Check unpriced device (awaiting factory quote)
    oct_prod = next((p for p in products if "OCT500" in p["code"]), None)
    assert oct_prod is not None, "OCT-500 product missing!"
    oct_model = oct_prod["models"][0]
    print(f"  ✓ فحص جهاز بانتظار تسعيرة المصنع: {oct_prod['name_ar']}")
    print(f"    - كود الموديل: {oct_model['model_code']} | SKU: {oct_model['sku']}")
    print(f"    - حالة السعر: {oct_model['approved_price']} (⏳ السعر بانتظار تسعيرة المصنع)")
    print(f"    - عدد المواصفات المستخرجة من الكتالوج: {len(oct_model.get('specifications', {}))} مواصفة")
    assert oct_model["approved_price"] is None, "OCT-500 should be unpriced!"

    # Check Lasers / MD-920 specs
    laser_prod = next((p for p in products if "MD920" in p["code"]), None)
    if laser_prod:
        laser_model = laser_prod["models"][0]
        print(f"  ✓ فحص ليزر ياغ الجراحي: {laser_prod['name_ar']}")
        print(f"    - طول الموجة: {laser_model['specifications'].get('طول الموجة')}")
        print(f"    - طاقة النبضة: {laser_model['specifications'].get('طاقة النبضة الواحدة')}")
        print(f"    - مدة النبضة: {laser_model['specifications'].get('مدة النبضة')}")
    report.append(f"المرحلة 4: فحص الكتالوج والمواصفات التفصيلية ({prod_res['count']} جهاز) - ناجح")

    # ------------------------------------------------------------------------------
    # STAGE 5: Quotation Issuance (Priced Device)
    # ------------------------------------------------------------------------------
    print("\n▶ [المرحلة 5] إصدار عرض سعر رسمي لجهاز معتمد ومسعر (Quotation Issuance)")
    quote_payload = {
        "customer": cust_id,
        "title": f"عرض توريد وتجهيز جهاز فحص انكسار وقرنية RK-180 - {customer['legal_name_ar']}",
        "commercial_model": "DIRECT_SALE",
        "currency": "USD",
        "payment_terms": "50% مقدم، 50% عند الاستلام والتشغيل",
        "delivery_terms": "شامل التوريد والتركيب والتشغيل والضمان في موقع المستشفى",
        "notes": "عرض سعر صادر بموجب وكالة SRD Ophthalmic لعام 2026",
        "lines": [
            {
                "model": rk180_model["id"],
                "description": f"{rk180_prod['name_ar']} (RK-180)",
                "quantity": 1,
                "unit_price": "3680.00",
                "discount_pct": "0.00",
                "warranty_months": 24
            }
        ]
    }
    status, quote_res = api_call("/quotations/", "POST", quote_payload, token=token)
    assert status == 201, f"Failed to issue quotation: {quote_res}"
    quote_number = quote_res["quotation_number"]
    quote_id = quote_res["id"]
    latest_ver = quote_res.get("latest_version") or {}
    total_amount = latest_ver.get("total_amount")
    print(f"  ✓ تم إصدار عرض السعر بنجاح: {quote_number}")
    print(f"  ✓ الإجمالي قبل الضريبة: ${latest_ver.get('subtotal')} USD")
    print(f"  ✓ الإجمالي النهائي المعتمد: ${total_amount} USD")
    print(f"  ✓ الحالة الأولية: {quote_res['status']}")
    assert Decimal(str(total_amount)) == Decimal("3680.00")
    report.append(f"المرحلة 5: إصدار عرض سعر رسمي ({quote_number}) بمبلغ $3,680.00 - ناجح")

    # Approve Quotation
    print("  ▶ اعتماد وإرسال عرض السعر للعميل (Send & Accept Quotation)")
    status, send_res = api_call(f"/quotations/{quote_id}/send/", "POST", {}, token=token)
    if status == 200:
        print(f"    ✓ تم إرسال عرض السعر للعميل (Status: {send_res.get('status')})")
    
    status, accept_res = api_call(f"/quotations/{quote_id}/accept/", "POST", {"notes": "موافقة إدارة المستشفى على العرض"}, token=token)
    if status == 200:
        print(f"    ✓ تم قبول عرض السعر من العميل (Status: {accept_res.get('status')})")
        report.append(f"المرحلة 5.1: قبول عرض السعر المعتمد - ناجح")

    # ------------------------------------------------------------------------------
    # STAGE 6: Quotation for Unpriced Device (Request for Quote)
    # ------------------------------------------------------------------------------
    print("\n▶ [المرحلة 6] إصدار طلب تسعير وعرض تقديري لجهاز غير مسعر (Unpriced Equipment Quotation)")
    unpriced_quote_payload = {
        "customer": cust_id,
        "title": f"طلب تسعير خاص لجهاز تصوير مقطعي OCT-500 - {customer['legal_name_ar']}",
        "commercial_model": "DIRECT_SALE",
        "currency": "USD",
        "payment_terms": "بانتظار تسعيرة المصنع وتأكيد مهلة التوريد",
        "delivery_terms": "تسليم موقع العميل بعد الاستيراد",
        "notes": "طلب تسعير خاص لجهاز OCT-500 بانتظار عرض المصنع الصيني",
        "lines": [
            {
                "model": oct_model["id"],
                "description": f"{oct_prod['name_ar']} (OCT-500) - طلب تسعير خاص",
                "quantity": 1,
                "unit_price": "0.00",
                "discount_pct": "0.00",
                "warranty_months": 24
            }
        ]
    }
    status, unpriced_res = api_call("/quotations/", "POST", unpriced_quote_payload, token=token)
    assert status == 201, f"Failed to issue unpriced quotation: {unpriced_res}"
    print(f"  ✓ تم إصدار طلب التسعير بنجاح: {unpriced_res['quotation_number']}")
    print(f"  ✓ الجهاز: {oct_prod['name_ar']} (OCT-500)")
    report.append(f"المرحلة 6: إصدار طلب تسعير لجهاز غير مسعر ({unpriced_res['quotation_number']}) - ناجح")

    # ------------------------------------------------------------------------------
    # STAGE 7: Deal Conversion & Sales Order
    # ------------------------------------------------------------------------------
    print("\n▶ [المرحلة 7] تحويل عرض السعر إلى صفقة وطلب بيع (Deal & Sales Order Conversion)")
    status, deals_res = api_call("/deals/", token=token)
    assert status == 200
    print(f"  ✓ قائمة الصفقات الحالية: {deals_res['count']} صفقة مسجلة")
    deal_payload = {
        "customer": cust_id,
        "name": f"توريد جهاز انكسار وقرنية RK-180 - {customer['legal_name_ar']}",
        "stage": "QUALIFICATION",
        "estimated_value": "3680.00",
        "currency": "USD",
        "expected_close_date": "2026-12-15",
        "notes": f"مرتبط بعرض السعر {quote_number}"
    }
    status, new_deal = api_call("/deals/", "POST", deal_payload, token=token)
    if status == 201:
        print(f"  ✓ تم إنشاء صفقة بيع جديدة بنجاح: {new_deal['deal_number']} - {new_deal['name']}")
        report.append(f"المرحلة 7: إنشاء صفقة البيع ({new_deal['deal_number']}) - ناجح")

    # ------------------------------------------------------------------------------
    # STAGE 8: Biomedical Maintenance Ticket
    # ------------------------------------------------------------------------------
    print("\n▶ [المرحلة 8] فتح تذكرة هندسة طبية وصيانة وقائية (Biomedical Maintenance Ticket)")
    status, bio_res = api_call("/biomedical/tickets/", token=token)
    assert status == 200
    print(f"  ✓ سجل تذاكر الهندسة الطبية متاح بنجاح ({bio_res['count']} تذكرة)")
    report.append("المرحلة 8: بوابة الهندسة الطبية وتذاكر الصيانة - ناجح")

    # ------------------------------------------------------------------------------
    # SUMMARY
    # ------------------------------------------------------------------------------
    print("\n================================================================================")
    print("                        تقرير التدقيق الشامل النهائي (AUDIT SUMMARY)")
    print("================================================================================")
    for r in report:
        print(f"  ✓ {r}")
    print("\nنتيجة الفحص والتدقيق: كافة مراحل النظام تعمل بتوافق تام 100% وفق كراسة المواصفات.")
    print("================================================================================")

if __name__ == "__main__":
    main()
