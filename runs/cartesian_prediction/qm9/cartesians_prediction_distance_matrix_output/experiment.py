from pathlib import Path
from tfn.tools.jobs import StructurePrediction


job = StructurePrediction(
    exp_config={
        "name": f"{Path(__file__).parent}",
        "notes": "",
        "loader_config": {
            "loader_type": "qm9_loader",
            "load_kwargs": {"modify_structures": True, "output_distance_matrix": True},
        },
        "builder_config": {
            "builder_type": "cartesian_builder",
            "prediction_type": "cartesians",
            "output_type": "distance_matrix",
        },
    }
)
job.run()