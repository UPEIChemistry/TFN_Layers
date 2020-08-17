from tfn.tools.jobs import SingleModel

job = SingleModel(
    exp_config={
        "name": "CARTESIAN TS MODEL ON TS DATASET",
        "notes": "Train on only distance matrix",
        "run_config": {"epochs": 200, "loss": "mae"},
        "builder_config": {
            "builder_type": "ts_builder",
            "num_layers": (2, 2, 2),
            "output_distance_matrix": False,
        },
        "loader_config": {
            "loader_type": "ts_loader",
            "load_kwargs": {"output_distance_matrix": False},
        },
    }
)
job.run()