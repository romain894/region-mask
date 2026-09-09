import marimo

__generated_with = "0.24.0"
app = marimo.App(width="medium")


@app.cell
def _():
    from pathlib import Path
    import marimo as mo
    from region_mask.pipeline import environment_settings, run_stage

    root = Path.cwd()
    return environment_settings, mo, root, run_stage


@app.cell
def _(mo):
    mo.md("""
    # Combine countries with oceans and seas

    Run country and ocean preparation first. This stage concatenates the two products.

    Settings come from `.env` in the launch directory (environment variables take precedence).
    **Generate and write** overwrites the configured outputs. For isolated validation,
    run `make regression` instead. Opening this notebook does not generate data.
    """)
    return


@app.cell
def _(environment_settings, mo, root):
    settings = environment_settings(root)
    generate = mo.ui.run_button(label="Generate and write", kind="warn")
    mo.vstack([mo.ui.table([{"setting": k, "value": v} for k, v in settings.items()],
                          selection=None), generate])
    return generate, settings


@app.cell
def _(generate, mo, root, run_stage, settings):
    mo.stop(not generate.value, mo.md("Ready. Review the settings before generating."))
    result = run_stage("countries_oceans", root=root, settings=settings)
    return (result,)


@app.cell
def _(mo, result):
    region = mo.ui.dropdown(options=result["ID"].tolist(), value=result["ID"].iloc[0],
                            label="Inspect region")
    mo.vstack([mo.ui.table(result.drop(columns="geometry"), selection=None), region])
    return (region,)


@app.cell
def _(region, result):
    from region_mask.plotting import plot_shape_region

    plot_shape_region(result, region.value)
    return


if __name__ == "__main__":
    app.run()
