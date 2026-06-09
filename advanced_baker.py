import bpy
import os
import time
import platform

bl_info = {
    "name": "Advanced Baker",
    "author": "Antigravity",
    "version": (2, 1, 0),
    "blender": (3, 2, 0),
    "location": "View3D > Sidebar > Adv Baker",
    "description": "Universal non-blocking baker with persistent queue and hardware detection.",
    "warning": "",
    "doc_url": "",
    "category": "Object",
}

# --- Properties ---

class AdvBakerObjectSettings(bpy.types.PropertyGroup):
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

class AdvBakerQueueItem(bpy.types.PropertyGroup):
    obj_ptr: bpy.props.PointerProperty(type=bpy.types.Object)
    system_name: bpy.props.StringProperty(name="System Name")
    progress: bpy.props.FloatProperty(name="Progress", default=0.0, min=0.0, max=100.0)
    status: bpy.props.EnumProperty(
        name="Status",
        items=[
            ('QUEUED', "Queued", "", "TIME", 1),
            ('BAKING', "Baking...", "", "PLAY", 2),
            ('DONE', "Done", "", "CHECKMARK", 3),
            ('ERROR', "Error", "", "CANCEL", 4),
            ('CANCELED', "Canceled", "", "PAUSE", 5)
        ],
        default='QUEUED'
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
    is_baking: bpy.props.BoolProperty(name="Is Baking", default=False)
    
# --- Hardware Detection ---

def get_hardware_info():
    cpu = platform.processor() or "Unknown CPU"
    gpus = []
    try:
        cycles_prefs = bpy.context.preferences.addons['cycles'].preferences
        if not hasattr(cycles_prefs, "devices") or not cycles_prefs.devices:
            cycles_prefs.get_devices()
        for device in cycles_prefs.devices:
            if device.type != 'CPU':
                gpus.append(device.name)
    except: pass
    gpu_str = ", ".join(gpus) if gpus else "None Detected (CPU Only)"
    return cpu, gpu_str

# --- Queue Management Operators ---

class ADVBAKER_OT_queue_add(bpy.types.Operator):
    bl_idname = "advbaker.queue_add"
    bl_label = "Add Selected"
    
    def execute(self, context):
        if context.scene.adv_baker.is_baking:
            self.report({'WARNING'}, "Cannot modify queue while baking!")
            return {'CANCELLED'}
            
        queue = context.scene.adv_baker_queue
        mode = context.scene.adv_baker.bake_mode
        added = 0
        
        for obj in context.selected_objects:
            if mode == 'PARTICLES':
                for mod in obj.modifiers:
                    if mod.type == 'PARTICLE_SYSTEM':
                        item = queue.add()
                        item.name = f"{obj.name} [{mod.name}]"
                        item.obj_ptr = obj
                        item.system_name = mod.name
                        item.status = 'QUEUED'
                        item.progress = 0.0
                        added += 1
            elif mode == 'TEXTURES' and obj.type == 'MESH':
                item = queue.add()
                item.name = f"{obj.name} [Texture]"
                item.obj_ptr = obj
                item.system_name = "Texture"
                item.status = 'QUEUED'
                item.progress = 0.0
                added += 1
                
        self.report({'INFO'}, f"Added {added} items to queue.")
        context.scene.adv_baker_active_index = max(0, len(queue) - 1)
        return {'FINISHED'}

class ADVBAKER_OT_queue_remove(bpy.types.Operator):
    bl_idname = "advbaker.queue_remove"
    bl_label = "Remove"
    
    def execute(self, context):
        if context.scene.adv_baker.is_baking:
            self.report({'WARNING'}, "Cannot modify queue while baking!")
            return {'CANCELLED'}
            
        queue = context.scene.adv_baker_queue
        idx = context.scene.adv_baker_active_index
        if 0 <= idx < len(queue):
            queue.remove(idx)
            context.scene.adv_baker_active_index = max(0, idx - 1)
        return {'FINISHED'}

class ADVBAKER_OT_queue_clear_completed(bpy.types.Operator):
    bl_idname = "advbaker.queue_clear_completed"
    bl_label = "Clear Completed"
    
    def execute(self, context):
        if context.scene.adv_baker.is_baking:
            self.report({'WARNING'}, "Cannot modify queue while baking!")
            return {'CANCELLED'}
            
        queue = context.scene.adv_baker_queue
        for i in range(len(queue) - 1, -1, -1):
            if queue[i].status in {'DONE', 'CANCELED', 'ERROR'}:
                queue.remove(i)
        context.scene.adv_baker_active_index = min(context.scene.adv_baker_active_index, max(0, len(queue)-1))
        return {'FINISHED'}

# --- Baking Operators ---

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
    bl_idname = "advbaker.bake_particles_modal"
    bl_label = "Bake Queue (Particles)"
    
    queue_index: bpy.props.IntProperty(name="Queue Index", default=-1, options={'HIDDEN'})
    
    _timer = None
    _queue_items = []
    _current_item_index = 0
    _current_frame = 1
    
    def modal(self, context, event):
        if event.type == 'ESC':
            if self._current_item_index < len(self._queue_items):
                self._queue_items[self._current_item_index].status = 'CANCELED'
            self.cancel(context)
            return {'CANCELLED'}

        if event.type == 'TIMER':
            try:
                if self._current_item_index >= len(self._queue_items):
                    self.finish(context)
                    return {'FINISHED'}
                    
                item = self._queue_items[self._current_item_index]
                obj = item.obj_ptr
                
                if not obj:
                    item.status = 'ERROR'
                    self._current_item_index += 1
                    return {'PASS_THROUGH'}
                
                if not getattr(obj, "visible_get", lambda: True)():
                    item.status = 'ERROR'
                    self._current_item_index += 1
                    return {'PASS_THROUGH'}
                
                mod = obj.modifiers.get(item.system_name)
                if not mod or not mod.show_viewport:
                    item.status = 'ERROR'
                    self._current_item_index += 1
                    return {'PASS_THROUGH'}
                
                obj_settings = obj.adv_baker
                
                if self._current_frame == 0:
                    self._current_frame = obj_settings.start_frame
                    item.status = 'BAKING'
                    item.progress = 0.0
                    
                    with context.temp_override(active_object=obj, object=obj):
                        try:
                            bpy.ops.ptcache.free_bake_all()
                        except: pass
                
                context.scene.frame_set(self._current_frame)
                
                if getattr(context, "area", None):
                    context.area.tag_redraw()
                
                frame_span = max(1, obj_settings.end_frame - obj_settings.start_frame)
                raw_progress = ((self._current_frame - obj_settings.start_frame) / frame_span) * 100.0
                item.progress = min(100.0, max(0.0, raw_progress))
                
                self._current_frame += 1
                
                if self._current_frame > obj_settings.end_frame:
                    item.status = 'DONE'
                    item.progress = 100.0
                    self._current_item_index += 1
                    self._current_frame = 0 
            except Exception as e:
                if self._current_item_index < len(self._queue_items):
                    self._queue_items[self._current_item_index].status = 'ERROR'
                self.report({'ERROR'}, f"Bake failed: {e}")
                self.cancel(context)
                return {'CANCELLED'}

        return {'PASS_THROUGH'}

    def execute(self, context):
        if context.scene.adv_baker.auto_save and bpy.data.is_saved:
            bpy.ops.wm.save_mainfile()
            
        queue = context.scene.adv_baker_queue
        if self.queue_index != -1 and 0 <= self.queue_index < len(queue):
            item = queue[self.queue_index]
            item.status = 'QUEUED'
            self._queue_items = [item]
        else:
            self._queue_items = [item for item in queue if item.status in {'QUEUED', 'ERROR', 'CANCELED'}]
        
        if not self._queue_items:
            self.report({'WARNING'}, "No valid queued items to bake.")
            return {'CANCELLED'}
            
        context.scene.adv_baker.is_baking = True
        self._current_item_index = 0
        self._current_frame = 0
        
        wm = context.window_manager
        self._timer = wm.event_timer_add(0.01, window=context.window)
        wm.modal_handler_add(self)
        
        self.report({'INFO'}, f"Started batch baking. Press ESC to abort.")
        return {'RUNNING_MODAL'}

    def cancel(self, context):
        context.scene.adv_baker.is_baking = False
        if self._timer:
            context.window_manager.event_timer_remove(self._timer)
            self._timer = None
        if getattr(context, "workspace", None) and hasattr(context.workspace, "status_text_set"):
            context.workspace.status_text_set(None)
        self.report({'WARNING'}, "Baking Aborted")

    def finish(self, context):
        context.scene.adv_baker.is_baking = False
        if self._timer:
            context.window_manager.event_timer_remove(self._timer)
            self._timer = None
        if getattr(context, "workspace", None) and hasattr(context.workspace, "status_text_set"):
            context.workspace.status_text_set(None)
            
        if context.scene.adv_baker.auto_pack:
            try:
                bpy.ops.image.pack()
            except: pass
            
        self.report({'INFO'}, "Batch Baking Complete")
        
class ADVBAKER_OT_bake_textures_modal(bpy.types.Operator):
    bl_idname = "advbaker.bake_textures_modal"
    bl_label = "Bake Queue (Textures)"
    
    queue_index: bpy.props.IntProperty(name="Queue Index", default=-1, options={'HIDDEN'})
    
    _timer = None
    _queue_items = []
    _current_item_index = 0
    
    def modal(self, context, event):
        if event.type == 'ESC':
            if self._current_item_index < len(self._queue_items):
                self._queue_items[self._current_item_index].status = 'CANCELED'
            self.cancel(context)
            return {'CANCELLED'}

        if event.type == 'TIMER':
            try:
                if self._current_item_index >= len(self._queue_items):
                    self.finish(context)
                    return {'FINISHED'}
                    
                item = self._queue_items[self._current_item_index]
                item.status = 'BAKING'
                obj = item.obj_ptr
                
                if getattr(context, "area", None):
                    context.area.tag_redraw()
                    
                if not obj or not getattr(obj, "visible_get", lambda: True)() or not obj.active_material or not obj.active_material.use_nodes:
                    item.status = 'ERROR'
                    self._current_item_index += 1
                    return {'PASS_THROUGH'}
                
                obj_settings = obj.adv_baker
                res = 1024
                if obj_settings.quality == 'LIGHT': res = 512
                elif obj_settings.quality == 'MEDIUM': res = 1024
                elif obj_settings.quality == 'HIGH': res = 2048
                
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
                
                item.progress = 50.0
                
                with context.temp_override(active_object=obj, object=obj):
                    try:
                        bpy.ops.object.bake(type='DIFFUSE', save_mode='INTERNAL')
                        item.status = 'DONE'
                        item.progress = 100.0
                    except Exception as e:
                        item.status = 'ERROR'
                
                self._current_item_index += 1
            except Exception as e:
                if self._current_item_index < len(self._queue_items):
                    self._queue_items[self._current_item_index].status = 'ERROR'
                self.cancel(context)
                return {'CANCELLED'}
            
        return {'PASS_THROUGH'}

    def execute(self, context):
        if context.scene.adv_baker.auto_save and bpy.data.is_saved:
            bpy.ops.wm.save_mainfile()
            
        queue = context.scene.adv_baker_queue
        if self.queue_index != -1 and 0 <= self.queue_index < len(queue):
            item = queue[self.queue_index]
            item.status = 'QUEUED'
            self._queue_items = [item]
        else:
            self._queue_items = [item for item in queue if item.status in {'QUEUED', 'ERROR', 'CANCELED'} and item.system_name == "Texture"]
        
        if not self._queue_items:
            self.report({'WARNING'}, "No valid queued items for textures.")
            return {'CANCELLED'}
            
        context.scene.adv_baker.is_baking = True
        self._current_item_index = 0
        
        wm = context.window_manager
        self._timer = wm.event_timer_add(0.5, window=context.window)
        wm.modal_handler_add(self)
        
        self.report({'INFO'}, f"Started Texture Batch. Press ESC to cancel.")
        return {'RUNNING_MODAL'}
        
    def cancel(self, context):
        context.scene.adv_baker.is_baking = False
        if self._timer:
            context.window_manager.event_timer_remove(self._timer)
            self._timer = None
        self.report({'WARNING'}, "Texture Baking Canceled")

    def finish(self, context):
        context.scene.adv_baker.is_baking = False
        if self._timer:
            context.window_manager.event_timer_remove(self._timer)
            self._timer = None
        
        if context.scene.adv_baker.auto_pack:
            try:
                bpy.ops.image.pack()
            except: pass
            
        self.report({'INFO'}, "Texture Baking Complete")

class ADVBAKER_OT_open_donation(bpy.types.Operator):
    bl_idname = "advbaker.open_donation"
    bl_label = "Support Us"
    def execute(self, context):
        import webbrowser
        webbrowser.open("https://ko-fi.com/faisalabusadahakafi9h")
        return {'FINISHED'}

# --- UI Lists and Panels ---

class ADVBAKER_UL_queue_list(bpy.types.UIList):
    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        row = layout.row(align=True)
        
        if not item.obj_ptr:
            row.label(text="<Deleted>", icon='GHOST')
        else:
            row.label(text=item.name, icon='OBJECT_DATA')
            
        if item.status == 'BAKING':
            row.prop(item, "progress", text="", slider=True)
            row.label(text="", icon='TIME')
        else:
            if item.status == 'QUEUED':
                row.label(text="Queued", icon='TIME')
            elif item.status == 'DONE':
                row.label(text="Done", icon='CHECKMARK')
            elif item.status == 'ERROR':
                row.label(text="Error", icon='CANCEL')
            elif item.status == 'CANCELED':
                row.label(text="Canceled", icon='PAUSE')
                
            if not context.scene.adv_baker.is_baking:
                mode = context.scene.adv_baker.bake_mode
                op_idname = "advbaker.bake_particles_modal" if mode == 'PARTICLES' else "advbaker.bake_textures_modal"
                op = row.operator(op_idname, icon='PLAY', text="")
                op.queue_index = index

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
        
        # --- Hardware Info ---
        cpu, gpu = get_hardware_info()
        sys_box = layout.box()
        sys_box.label(text="System Hardware", icon='DESKTOP')
        col = sys_box.column(align=True)
        col.row().label(text=f"CPU: {cpu}")
        col.row().label(text=f"GPU: {gpu}")
        
        layout.separator()
        layout.prop(settings, "bake_mode", expand=True)
        
        box = layout.box()
        box.label(text="Global Queue & Safety", icon='LOCKED')
        box.prop(settings, "auto_save")
        box.prop(settings, "auto_pack")
        
        layout.separator()
        
        # --- BIG BAKE BUTTONS ---
        is_locked = settings.is_baking
        col = layout.column()
        col.enabled = not is_locked
        if settings.bake_mode == 'PARTICLES':
            col.operator("advbaker.bake_particles_modal", icon='PHYSICS', text="Bake All Queued (Particles)")
        else:
            col.operator("advbaker.bake_textures_modal", icon='TEXTURE', text="Bake All Queued (Textures)")
            
        layout.separator()
        
        # --- OLD PER-OBJECT OVERRIDES ---
        layout.label(text="Per-Object Overrides:")
        
        obj = context.active_object
        if obj:
            layout.label(text=f"Active: {obj.name}", icon='OBJECT_DATA')
            obj_settings = obj.adv_baker
            col = layout.column(align=True)
            if settings.bake_mode == 'PARTICLES':
                col.prop(obj_settings, "start_frame")
                col.prop(obj_settings, "end_frame")
            else:
                col.prop(obj_settings, "quality")
        else:
            layout.label(text="Select an object to see settings.", icon='ERROR')
            
        layout.separator()
        
        # --- ADDED QUEUE UI ---
        box = layout.box()
        box.label(text="Live Bake Queue", icon='MENU_PANEL')
        
        row = box.row()
        row.template_list("ADVBAKER_UL_queue_list", "", scene, "adv_baker_queue", scene, "adv_baker_active_index", rows=4)
        
        col = row.column(align=True)
        col.operator("advbaker.queue_add", icon='ADD', text="")
        col.operator("advbaker.queue_remove", icon='REMOVE', text="")
        col.operator("advbaker.queue_clear_completed", icon='TRASH', text="")
        
        layout.separator()
        layout.operator("advbaker.open_donation", icon='FUND')

# --- Registration ---

classes = (
    AdvBakerObjectSettings,
    AdvBakerQueueItem,
    AdvBakerSceneSettings,
    ADVBAKER_OT_queue_add,
    ADVBAKER_OT_queue_remove,
    ADVBAKER_OT_queue_clear_completed,
    ADVBAKER_OT_free_all_caches,
    ADVBAKER_OT_bake_particles_modal,
    ADVBAKER_OT_bake_textures_modal,
    ADVBAKER_OT_open_donation,
    ADVBAKER_UL_queue_list,
    ADVBAKER_PT_main_panel,
)

def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    bpy.types.Object.adv_baker = bpy.props.PointerProperty(type=AdvBakerObjectSettings)
    bpy.types.Scene.adv_baker = bpy.props.PointerProperty(type=AdvBakerSceneSettings)
    bpy.types.Scene.adv_baker_queue = bpy.props.CollectionProperty(type=AdvBakerQueueItem)
    bpy.types.Scene.adv_baker_active_index = bpy.props.IntProperty(name="Active Queue Index", default=0)

def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
    del bpy.types.Object.adv_baker
    del bpy.types.Scene.adv_baker
    del bpy.types.Scene.adv_baker_queue
    del bpy.types.Scene.adv_baker_active_index

if __name__ == "__main__":
    register()
