Generators for Scarbound_Car_v10_DetailedCar (Blender 5.2.2, run against the live session via the blender_mcp socket
127.0.0.1:9876 with bb.py, or adapt prelude.py's SP path). Order:
  apply_gun, apply_body, apply_details, apply_wheels, apply_under, apply_harpoon,
  apply_quasi_body, apply_quasi_head, apply_quasi_limbs  ->  uv_final -> make_lods -> bake.py (headless)
  -> baked_mats -> export_fbx -> verify_fbx.py (headless); QA: qa_aim.py, qa_aim2.py, qa_run.sh
lib/: mb.py (mesh builder), carshape.py (port of ModelsCar shape functions), parts_*.py (geometry),
      mats.py (surface materials), organic.py (remesh/sculpt pipeline).
