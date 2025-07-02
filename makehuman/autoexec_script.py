from core import G
human = G.app.selectedHuman

# Set a modifier by name
modifier = human.getModifier('macrodetails/Age')
modifier.setValue(0.1)  # 1.0 = fully male, 0.0 = fully female

# Apply all changes to update the mesh
human.applyAllTargets()
