import sys
import subprocess

try:
    import arabic_reshaper
    from bidi.algorithm import get_display
except ImportError:
    subprocess.check_call([sys.executable, "-m", "pip", "install", "arabic-reshaper", "python-bidi"])
    import arabic_reshaper
    from bidi.algorithm import get_display

strings = {
    "Advanced Baker": "الخابز المتقدم",
    "System Hardware": "مواصفات الجهاز",
    "Particle Physics": "فيزياء الجزيئات",
    "Texture / Render": "الخامات / الرندر",
    "Global Queue & Safety": "القائمة العامة والأمان",
    "Pre-Bake Auto-Save": "حفظ تلقائي قبل الخبز",
    "Post-Bake Auto-Pack": "حزم ملفات العمل تلقائياً",
    "Bake All Queued (Particles)": "خبز كامل القائمة (جزيئات)",
    "Bake All Queued (Textures)": "خبز كامل القائمة (خامات)",
    "Bake Active Object Only": "خبز العنصر المحدد فقط",
    "Per-Object Overrides:": "إعدادات العناصر المستقلة:",
    "Active:": "النشط:",
    "Start Frame": "إطار البداية",
    "End Frame": "إطار النهاية",
    "Quality": "الجودة",
    "Low": "خفيف",
    "Medium": "متوسط",
    "High": "عالي",
    "Select an object to see settings.": "الرجاء تحديد عنصر لرؤية الإعدادات.",
    "Live Bake Queue": "قائمة الخبز المباشرة",
    "Support Us": "ادعمنا",
    "Queued": "في الانتظار",
    "Baking...": "جاري الخبز...",
    "Done": "تم",
    "Error": "خطأ",
    "Canceled": "تم الإلغاء",
    "Add Selected": "إضافة المحدد",
    "Remove": "إزالة",
    "Clear Completed": "مسح المكتمل",
    "Bake Queue (Particles)": "خبز القائمة (جزيئات)",
    "Bake Queue (Textures)": "خبز القائمة (خامات)",
    "Queue Index": "مؤشر القائمة",
    "Status": "الحالة",
    "Progress": "التقدم",
    "System Name": "اسم النظام",
    "Bake Mode": "وضع الخبز",
    "Is Baking": "جاري الخبز",
    "<Deleted>": "<محذوف>",
    "CPU:": "المعالج:",
    "GPU:": "كرت الشاشة:",
}

out = "{\n"
for k, v in strings.items():
    reshaped = arabic_reshaper.reshape(v)
    bidi_text = get_display(reshaped)
    out += f'        ("*", "{k}"): "{bidi_text}",\n'
out += "}"
with open("arabic_dict.txt", "w", encoding="utf-8") as f:
    f.write(out)
