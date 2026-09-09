"""Optional inspection figures; never modify or export the scientific outputs."""

import matplotlib.pyplot as plt


def plot_shape_region(regions, region_id):
    selected = regions.loc[regions["ID"] == region_id]
    fig, ax = plt.subplots(figsize=(10, 5))
    selected.boundary.plot(ax=ax)
    ax.set(title=str(selected["NAME"].iloc[0]), xlabel="Longitude", ylabel="Latitude")
    plt.close(fig)
    return fig


def plot_mask_region(result, region_id):
    fig, ax = plt.subplots(figsize=(10, 5))
    result.mask.sel(region=region_id).plot(ax=ax, cmap="GnBu", vmin=0, vmax=1)
    result.regions.loc[result.regions["ID"] == region_id].boundary.plot(
        ax=ax, color="black", linewidth=0.5)
    ax.set_title(f"Fractional mask: {region_id}")
    plt.close(fig)
    return fig


def plot_raw_coverage(result):
    # Simplification is only for the figure, as in the original notebook.
    regions = result.regions.copy()
    regions.geometry = regions.simplify(tolerance=0.05, preserve_topology=False)
    coverage = result.raw_mask.sum(dim="region")
    fig, ax = plt.subplots(figsize=(12, 5))
    coverage.plot(ax=ax, vmin=0, vmax=2, robust=False, cmap="BrBG")
    regions.boundary.plot(ax=ax, color="red", linewidth=0.1)
    ax.set_title(f"Before normalization: sum min={coverage.min().item():.2f}, "
                 f"max={coverage.max().item():.2f}")
    hist, hist_ax = plt.subplots(figsize=(12, 3))
    coverage.plot.hist(ax=hist_ax, bins=50, color="teal", edgecolor="black", linewidth=0.5)
    hist_ax.set(yscale="log", title="Distribution before normalization",
                xlabel="Sum of fractional coverage", ylabel="Number of pixels")
    plt.close(fig)
    plt.close(hist)
    return fig, hist
