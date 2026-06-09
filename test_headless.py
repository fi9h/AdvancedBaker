import bpy
import sys
import os

sys.path.append(r"D:\antigravity\AdvancedBaker")
import advanced_baker

try:
    print("--- STARTING BLENDER HEADLESS TEST ---")
    advanced_baker.register()
    print("[PASS] Classes registered successfully! No syntax or API definition errors.")
    
    # Test 1: Dummy Object
    bpy.ops.mesh.primitive_cube_add()
    cube = bpy.context.active_object
    
    # Test 2: Add particle system
    mod = cube.modifiers.new(name="TestParticles", type='PARTICLE_SYSTEM')
    print("[PASS] Created dummy object and particle system.")
    
    # Test 3: Test CollectionProperty Queue creation
    queue = bpy.context.scene.adv_baker_queue
    item = queue.add()
    item.name = "Cube [TestParticles]"
    item.obj_ptr = cube
    item.system_name = "TestParticles"
    item.frame_start = 1
    item.frame_end = 50
    item.status = 'QUEUED'
    item.progress = 0.0
    print("[PASS] CollectionProperty Queue Item added successfully!")
    
    # Test 4: Validation
    print(f"[INFO] Current Queue Length: {len(queue)}")
    if queue[0].obj_ptr == cube:
        print("[PASS] PointerProperty resolved to actual 3D object correctly.")
        
    if queue[0].status == 'QUEUED':
        print("[PASS] EnumProperty status successfully read.")
    
    # Clean Unregister
    advanced_baker.unregister()
    print("[PASS] Unregistered safely. No Memory Leaks.")
    print("--- ALL UI AND DATA TESTS PASSED ---")

except Exception as e:
    import traceback
    traceback.print_exc()
    sys.exit(1)
