"""Shared ¾ camera that fills the frame with the airframe."""

from __future__ import annotations

import numpy as np
import pyvista as pv


def frame_full_airframe(plotter: pv.Plotter, wall: pv.DataSet, *, zoom: float = 1.75) -> None:
    """Fit the airframe AABB, then swing to a nose-left ¾ view and tighten."""
    b = tuple(float(x) for x in wall.bounds)
    plotter.disable_parallel_projection()
    plotter.reset_camera(bounds=b)
    focal = np.asarray(plotter.camera.focal_point, dtype=float)
    dist = float(np.linalg.norm(np.asarray(plotter.camera.position) - focal))
    direction = np.array([0.60, -0.70, 0.38], dtype=float)
    direction /= float(np.linalg.norm(direction))
    plotter.camera.position = (focal + dist * direction).tolist()
    plotter.camera.focal_point = focal.tolist()
    plotter.camera.up = (0.0, 0.0, 1.0)
    plotter.camera.zoom(zoom)
