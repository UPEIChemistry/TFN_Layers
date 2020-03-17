from tfn.tools.jobs import Pipeline


job = Pipeline({
    'run_config': {
        'name': 'tl0 - QM9 Energy to ISO17 Energy/Force predictor',
        'notes': 'Not freezing layers, defaults for both models'
    },
    'pipeline_config': {
        'configs': [
            {  # Energy config
                'builder_config': {
                    'builder_type': 'force_builder'
                },
                'loader_config': {
                    'loader_type': 'sn2_loader'
                }
            },
            {  # Force config
                'builder_config': {
                    'builder_type': 'ts_builder'
                },
                'loader_config': {
                    'loader_type': 'ts_loader',
                    'splitting': '90:10'
                }
            }
        ]
    }
})
job.run()