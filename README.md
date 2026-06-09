# Advanced Baker for Blender 3.0+

A robust, non-blocking baking add-on for Blender that handles both **Particle Physics Simulations** and **Texture / Render Baking** seamlessly. 

## The Problem It Solves
Natively, automating baking in Blender can be incredibly frustrating due to `context is incorrect` errors and the fact that heavy bakes lock the UI thread, causing the operating system to tag Blender as "App Not Responding". 

**Advanced Baker** solves this by:
1. Using strict context overrides (`context.temp_override`) to ensure baking never fails due to incorrect selection states.
2. Utilizing **Modal Operators** that yield control back to the UI, entirely preventing "App Not Responding" lockups.
3. Displaying **Real-Time Dynamic ETAs** and **Hardware Capabilities**.

## Features
- **No More UI Freezes:** Modal timers keep Blender responsive even during massive batches.
- **Hardware Detection & ETA:** Reads your exact CPU and GPU configuration and calculates a live ETA based on actual processing speed.
- **Auto-Node Setup:** Automatically creates and assigns Image Texture nodes for Cycles baking so you don't have to manually connect nodes for 50 different objects.
- **Infinite Scaling:** No arbitrary frame limits (supports up to 10,000,000 frames).
- **Batch Processing:** Select multiple objects, configure their overrides, and bake them sequentially.

## Support Us
If you find this add-on useful and it saves you hours of baking headaches, please consider supporting us on Ko-fi!
☕ [Support Us](https://ko-fi.com/faisalabusadahakafi9h)

## Installation
1. Download `advanced_baker.py` from this repository.
2. Open Blender and go to **Edit > Preferences > Add-ons**.
3. Click **Install...**, select the downloaded `advanced_baker.py` file, and enable it.
4. Press `N` in the 3D Viewport to open the sidebar and look for the **Adv Baker** tab.

## Usage
1. Select the objects you wish to bake in the 3D Viewport.
2. Open the **Adv Baker** N-Panel.
3. Choose either **Particle Physics** or **Texture / Render** mode.
4. Set global settings (Auto-Save, Auto-Pack).
5. Adjust Per-Object settings (Start/End frames, Quality).
6. Click **Bake All Queued** and check the status bar / system console for live progress!

## License
MIT License. Open source and free to use for any commercial or non-commercial projects.
