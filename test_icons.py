import bpy
import sys

valid_icons = bpy.types.UILayout.bl_rna.functions["prop"].parameters["icon"].enum_items.keys()

missing = []
for test_icon in ['DESKTOP', 'LOCKED', 'PHYSICS', 'TEXTURE', 'OBJECT_DATA', 'ERROR', 'MENU_PANEL', 'ADD', 'REMOVE', 'TRASH', 'FUND', 'GHOST', 'TIME', 'PLAY', 'CHECKMARK', 'CANCEL', 'PAUSE']:
    if test_icon not in valid_icons:
        missing.append(test_icon)

with open(r"D:\antigravity\AdvancedBaker\icon_report.txt", "w") as f:
    f.write(f"Missing: {missing}")

sys.exit(0)
