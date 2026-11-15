import os
import fitz

pdf_path = "media/documents/2026/11/SRD_Ophthalmic_Equipment_Catalogue.pdf"
doc = fitz.open(pdf_path)
out_dir = "media/models/extracted"
os.makedirs(out_dir, exist_ok=True)

print(f"Total pages: {len(doc)}")
for pno in range(len(doc)):
    page = doc[pno]
    image_list = page.get_images(full=True)
    if not image_list:
        continue
    # Pick the best image for the device
    best_img = None
    best_area = 0
    for img_idx, img in enumerate(image_list):
        xref = img[0]
        base_image = doc.extract_image(xref)
        w, h = base_image["width"], base_image["height"]
        # Skip small icons, logos, or thin headers
        if w < 180 or h < 180:
            continue
        # Also skip aspect ratios that are banner lines (w/h > 4 or h/w > 4)
        aspect = w / h
        if aspect > 3.5 or aspect < 0.28:
            continue
        area = w * h
        if area > best_area:
            best_area = area
            best_img = (xref, base_image)

    if best_img:
        xref, bimg = best_img
        ext = bimg["ext"]
        out_path = os.path.join(out_dir, f"page_{pno+1}_xref_{xref}.{ext}")
        with open(out_path, "wb") as f:
            f.write(bimg["image"])
        print(f"P{pno+1}: Saved {out_path} ({bimg['width']}x{bimg['height']})")
