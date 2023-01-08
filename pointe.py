import modal

stub = modal.Stub("pointe")

image = (
    modal.Image.debian_slim()
    .apt_install(["git"])
    .pip_install(["git+https://github.com/openai/point-e"])
)

volume = modal.SharedVolume().persist("model-cache-vol")
cache_path = "/root/point_e_model_cache"

stub.image = image


class PointE:
    @stub.function(
        gpu="A10G",
        shared_volumes={cache_path: volume},
    )
    def run_pointe(self, prompt: str):
        import torch
        from point_e.diffusion.configs import DIFFUSION_CONFIGS, diffusion_from_config
        from point_e.diffusion.sampler import PointCloudSampler
        from point_e.models.configs import MODEL_CONFIGS, model_from_config
        from point_e.models.download import load_checkpoint
        from point_e.util.pc_to_mesh import marching_cubes_mesh
        from tqdm.auto import tqdm

        print("Running PointE in Modal")
        device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

        print("creating base model...")
        base_name = "base40M-textvec"
        base_model = model_from_config(MODEL_CONFIGS[base_name], device)
        base_model.eval()
        base_diffusion = diffusion_from_config(DIFFUSION_CONFIGS[base_name])

        print("creating upsample model...")
        upsampler_model = model_from_config(MODEL_CONFIGS["upsample"], device)
        upsampler_model.eval()
        upsampler_diffusion = diffusion_from_config(DIFFUSION_CONFIGS["upsample"])

        print("downloading base checkpoint...")
        base_model.load_state_dict(load_checkpoint(base_name, device))

        print("downloading upsampler checkpoint...")
        upsampler_model.load_state_dict(load_checkpoint("upsample", device))

        sampler = PointCloudSampler(
            device=device,
            models=[base_model, upsampler_model],
            diffusions=[base_diffusion, upsampler_diffusion],
            num_points=[1024, 4096 - 1024],
            aux_channels=["R", "G", "B"],
            guidance_scale=[3.0, 0.0],
            model_kwargs_key_filter=(
                "texts",
                "",
            ),  # Do not condition the upsampler at all
        )

        # Produce a sample from the model.
        samples = None
        for x in tqdm(
            sampler.sample_batch_progressive(
                batch_size=1, model_kwargs=dict(texts=[prompt])
            )
        ):
            samples = x

        pc = sampler.output_to_point_clouds(samples)[0]

        print("creating SDF model...")
        name = "sdf"
        model = model_from_config(MODEL_CONFIGS[name], device)
        model.eval()

        print("loading SDF model...")
        model.load_state_dict(load_checkpoint(name, device))

        print("generating mesh...")
        return marching_cubes_mesh(
            pc=pc,
            model=model,
            batch_size=4096,
            grid_size=128,
            progress=True,
        )


def entrypoint(prompt: str):
    print(f"pointe prompt => {prompt}")

    with stub.run():
        pointe = PointE()
        return pointe.run_pointe.call(prompt)


if __name__ == "__main__":
    mesh = entrypoint("A golden pineapple")
    with open(f"mesh.ply", "wb") as f:
        mesh.write_ply(f)