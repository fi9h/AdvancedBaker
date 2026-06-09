import bpy
import os
import time
import platform

bl_info = {
    "name": "Advanced Baker",
    "author": "Antigravity",
    "version": (1, 2, 0),
    "blender": (3, 0, 0),
    "location": "View3D > Sidebar > Adv Baker",
    "description": "Universal non-blocking baker with anti-freeze and hardware detection.",
    "warning": "",
    "doc_url": "",
    "category": "Object",
}

# --- Properties ---

class AdvBakerObjectSettings(bpy.types.PropertyGroup):
    # Expanded max frames to an absurdly high number so there's practically no limit
    start_frame: bpy.props.IntProperty(name="Start Frame", default=1, min=1, max=10000000)
    end_frame: bpy.props.IntProperty(name="End Frame", default=250, min=1, max=10000000)
    quality: bpy.props.EnumProperty(
        name="Quality",
        items=[
            ('LIGHT', "Light", "Fast/Low quality"),
            ('MEDIUM', "Medium", "Balanced quality"),
            ('HIGH', "High", "Production quality")
        ],
        default='MEDIUM'
    )

class AdvBakerSceneSettings(bpy.types.PropertyGroup):
    bake_mode: bpy.props.EnumProperty(
        name="Bake Mode",
        items=[
            ('PARTICLES', "Particle Physics", "Bake particle system caches"),
            ('TEXTURES', "Texture / Render", "Bake render output to textures")
        ],
        default='PARTICLES'
    )
    auto_save: bpy.props.BoolProperty(name="Pre-Bake Auto-Save", default=False)
    auto_pack: bpy.props.BoolProperty(name="Post-Bake Auto-Pack", default=False)
    
# --- Hardware Detection ---

def get_hardware_info():
    """Detects CPU and available rendering GPUs in Blender"""
    cpu = platform.processor() or "Unknown CPU"
    gpus = []
    
    try:
        cycles_prefs = bpy.context.preferences.addons['cycles'].preferences
        if not hasattr(cycles_prefs, "devices") or not cycles_prefs.devices:
            cycles_prefs.get_devices()
            
        for device in cycles_prefs.devices:
            if device.type != 'CPU':
                gpus.append(device.name)
    except Exception as e:
        print(f"Hardware detection error: {e}")
        pass
        
    gpu_str = ", ".join(gpus) if gpus else "None Detected (CPU Only)"
    return cpu, gpu_str

# --- Operators ---

class ADVBAKER_OT_free_all_caches(bpy.types.Operator):
    """Free particle caches for all selected objects"""
    bl_idname = "advbaker.free_all_caches"
    bl_label = "Free All Selected Caches"
    
    def execute(self, context):
        count = 0
        for obj in context.selected_objects:
            if not obj.particle_systems:
                continue
            with context.temp_override(active_object=obj, object=obj):
                try:
                    bpy.ops.ptcache.free_bake_all()
                    count += 1
                except Exception as e:
                    self.report({'WARNING'}, f"Failed to free cache on {obj.name}: {str(e)}")
        self.report({'INFO'}, f"Freed caches on {count} objects.")
        return {'FINISHED'}

class ADVBAKER_OT_bake_particles_modal(bpy.types.Operator):
    """Bake particles sequentially without locking the UI, includes ETA"""
    bl_idname = "advbaker.bake_particles_modal"
    bl_label = "Bake Queued Particles"
    
    _timer = None
    _objects = []
    _current_obj_index = 0
    _current_frame = 1
    
    _start_time = 0
    _frames_baked = 0
    
    def modal(self, context, event):
        if event.type == 'ESC':
            self.cancel(context)
            return {'CANCELLED'}

        if event.type == 'TIMER':
            if self._current_obj_index >= len(self._objects):
                self.finish(context)
                return {'FINISHED'}
                
            obj = self._objects[self._current_obj_index]
            settings = obj.adv_baker
            
            # Initialization for this object
            if self._current_frame == 0: 
                self._current_frame = settings.start_frame
                self._start_time = time.time()
                self._frames_baked = 0
                
                print(f"--- Baking Object {self._current_obj_index + 1}/{len(self._objects)}: {obj.name} ---")
                
                # Free cache first with context override
                with context.temp_override(active_object=obj, object=obj):
                    try:
                        bpy.ops.ptcache.free_bake_all()
                    except: pass
            
            # Advance frame to simulate and cache
            context.scene.frame_set(self._current_frame)
            self._frames_baked += 1
            
            # Force UI Redraw so Windows/OS does not tag the app as "Not Responding"
            if context.area:
                context.area.tag_redraw()
            
            # Calculate Progress
            progress_range = max(1, (settings.end_frame - settings.start_frame))
            progress = ((self._current_frame - settings.start_frame) / progress_range) * 100
            
            # Calculate Dynamic ETA based on hardware processing speed
            elapsed_time = time.time() - self._start_time
            time_per_frame = elapsed_time / max(1, self._frames_baked)
            frames_remaining = settings.end_frame - self._current_frame
            
            eta_seconds = time_per_frame * frames_remaining
            eta_mins = int(eta_seconds // 60)
            eta_secs = int(eta_seconds % 60)
            eta_str = f"ETA: {eta_mins}m {eta_secs}s"
            
            # Send message to Blender's console and status bar
            msg = f"[{obj.name}] Frame {self._current_frame}/{settings.end_frame} ({progress:.1f}%) | {eta_str}"
            print(msg)
            context.workspace.status_text_set(msg)
            
            self._current_frame += 1
            
            # Check if object is done
            if self._current_frame > settings.end_frame:
                print(f"Finished baking {obj.name} in {int(elapsed_time//60)}m {int(elapsed_time%60)}s")
                self._current_obj_index += 1
                self._current_frame = 0 # reset for next object

        return {'PASS_THROUGH'}

    def execute(self, context):
        if context.scene.adv_baker.auto_save and bpy.data.is_saved:
            bpy.ops.wm.save_mainfile()
            
        self._objects = [o for o in context.selected_objects if o.particle_systems]
        if not self._objects:
            self.report({'WARNING'}, "No selected objects with particle systems.")
            return {'CANCELLED'}
            
        self._current_obj_index = 0
        self._current_frame = 0
        
        wm = context.window_manager
        self._timer = wm.event_timer_add(0.01, window=context.window)
        wm.modal_handler_add(self)
        
        self.report({'INFO'}, f"Started batch baking {len(self._objects)} objects. Press ESC to cancel.")
        return {'RUNNING_MODAL'}

    def cancel(self, context):
        wm = context.window_manager
        wm.event_timer_remove(self._timer)
        context.workspace.status_text_set(None)
        self.report({'WARNING'}, "Baking Cancelled by User")

    def finish(self, context):
        wm = context.window_manager
        wm.event_timer_remove(self._timer)
        context.workspace.status_text_set(None)
        
        self.report({'INFO'}, "Batch Baking Complete")
        print("Batch Baking Complete!")
        
        if context.scene.adv_baker.auto_pack:
            bpy.ops.image.pack()

class ADVBAKER_OT_bake_textures_modal(bpy.types.Operator):
    """Bake textures sequentially using a modal to prevent full batch freeze"""
    bl_idname = "advbaker.bake_textures"
    bl_label = "Bake Queued Textures"
    
    _timer = None
    _objects = []
    _current_obj_index = 0
    
    def modal(self, context, event):
        if event.type == 'ESC':
            self.cancel(context)
            return {'CANCELLED'}

        if event.type == 'TIMER':
            if self._current_obj_index >= len(self._objects):
                self.finish(context)
                return {'FINISHED'}
                
            obj = self._objects[self._current_obj_index]
            settings = obj.adv_baker
            
            print(f"Preparing texture bake for {obj.name} ({self._current_obj_index + 1}/{len(self._objects)})")
            context.workspace.status_text_set(f"Baking Texture for {obj.name}...")
            
            # Force UI redraw to update status text before the heavy C-level bake freezes it
            if context.area:
                context.area.tag_redraw()
            
            res = 1024
            if settings.quality == 'LIGHT': res = 512
            elif settings.quality == 'MEDIUM': res = 1024
            elif settings.quality == 'HIGH': res = 2048
            
            if obj.active_material and obj.active_material.use_nodes:
                tree = obj.active_material.node_tree
                nodes = tree.nodes
                
                img_name = f"{obj.name}_Bake"
                img = bpy.data.images.get(img_name)
                if not img:
                    img = bpy.data.images.new(img_name, width=res, height=res)
                
                tex_node = nodes.new('ShaderNodeTexImage')
                tex_node.image = img
                tex_node.name = "ADV_BAKER_NODE"
                nodes.active = tex_node
                
                with context.temp_override(active_object=obj, object=obj):
                    try:
                        # This single bake call will lock the UI temporarily,
                        # but breaking it into a modal prevents "App Not Responding" 
                        # for the ENTIRE duration of the 5-bird batch queue.
                        bpy.ops.object.bake(type='DIFFUSE', save_mode='INTERNAL')
                        print(f"[{obj.name}] Texture baked successfully.")
                    except Exception as e:
                        print(f"ERROR: {obj.name} failed to bake: {e}")
            else:
                print(f"ERROR: {obj.name} has no active node-based material. Skipping.")
            
            self._current_obj_index += 1
            
        return {'PASS_THROUGH'}

    def execute(self, context):
        if context.scene.adv_baker.auto_save and bpy.data.is_saved:
            bpy.ops.wm.save_mainfile()
            
        self._objects = [o for o in context.selected_objects if o.type == 'MESH']
        if not self._objects:
            self.report({'WARNING'}, "No valid mesh objects selected for texture baking.")
            return {'CANCELLED'}
            
        self._current_obj_index = 0
        
        wm = context.window_manager
        # Fire timer very slowly (0.5s) to ensure UI has time to redraw between heavy texture bakes
        self._timer = wm.event_timer_add(0.5, window=context.window)
        wm.modal_handler_add(self)
        
        self.report({'INFO'}, f"Started Texture Batch. Press ESC to cancel between objects.")
        return {'RUNNING_MODAL'}
        
    def cancel(self, context):
        wm = context.window_manager
        wm.event_timer_remove(self._timer)
        context.workspace.status_text_set(None)
        self.report({'WARNING'}, "Texture Baking Cancelled")

    def finish(self, context):
        wm = context.window_manager
        wm.event_timer_remove(self._timer)
        context.workspace.status_text_set(None)
        
        if context.scene.adv_baker.auto_pack:
            try:
                bpy.ops.image.pack()
            except: pass
            
        self.report({'INFO'}, "Texture Baking Complete")
        return {'FINISHED'}

class ADVBAKER_OT_open_donation(bpy.types.Operator):
    """Support us to keep improving this add-on"""
    bl_idname = "advbaker.open_donation"
    bl_label = "Support Us"
    
    def execute(self, context):
        import webbrowser
        webbrowser.open("https://ko-fi.com/faisalabusadahakafi9h")
        return {'FINISHED'}

# --- UI Panel ---

class ADVBAKER_PT_main_panel(bpy.types.Panel):
    bl_label = "Advanced Baker"
    bl_idname = "ADVBAKER_PT_main_panel"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'Adv Baker'
    
    def draw(self, context):
        layout = self.layout
        scene = context.scene
        settings = scene.adv_baker
        
        # --- System Hardware Info ---
        cpu, gpu = get_hardware_info()
        sys_box = layout.box()
        sys_box.label(text="System Hardware", icon='DESKTOP')
        
        col = sys_box.column(align=True)
        row = col.row()
        row.alignment = 'LEFT'
        row.label(text="CPU:")
        row.label(text=cpu)
        
        row2 = col.row()
        row2.alignment = 'LEFT'
        row2.label(text="GPU:")
        row2.label(text=gpu)
        # ----------------------------
        
        layout.separator()
        
        layout.prop(settings, "bake_mode", expand=True)
        
        box = layout.box()
        box.label(text="Global Queue & Safety", icon='LOCKED')
        box.prop(settings, "auto_save")
        box.prop(settings, "auto_pack")
        
        layout.separator()
        
        if settings.bake_mode == 'PARTICLES':
            layout.operator("advbaker.free_all_caches", icon='X')
            layout.operator("advbaker.bake_particles_modal", icon='PHYSICS', text="Bake All Queued (Particles)")
            layout.label(text="*Check System Console for live ETA", icon='INFO')
        else:
            layout.operator("advbaker.bake_textures", icon='TEXTURE', text="Bake All Queued (Textures)")
            
        layout.separator()
        layout.label(text="Per-Object Overrides:")
        
        obj = context.active_object
        if obj:
            layout.label(text=f"Active: {obj.name}", icon='OBJECT_DATA')
            obj_settings = obj.adv_baker
            col = layout.column(align=True)
            col.prop(obj_settings, "start_frame")
            col.prop(obj_settings, "end_frame")
            col.prop(obj_settings, "quality")
        else:
            layout.label(text="Select an object to see settings.", icon='ERROR')
            
        layout.separator()
        layout.operator("advbaker.open_donation", icon='FUND')

# --- Registration ---

classes = (
    AdvBakerObjectSettings,
    AdvBakerSceneSettings,
    ADVBAKER_OT_free_all_caches,
    ADVBAKER_OT_bake_particles_modal,
    ADVBAKER_OT_bake_textures_modal,
    ADVBAKER_OT_open_donation,
    ADVBAKER_PT_main_panel,
)

def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    bpy.types.Object.adv_baker = bpy.props.PointerProperty(type=AdvBakerObjectSettings)
    bpy.types.Scene.adv_baker = bpy.props.PointerProperty(type=AdvBakerSceneSettings)

def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
    del bpy.types.Object.adv_baker
    del bpy.types.Scene.adv_baker

if __name__ == "__main__":
    register()
