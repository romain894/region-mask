"""Controlled, non-publishing ocean experiments and a Markdown review atlas.

Run from a checkout: python -m regression.ocean_review --output NEW_DIRECTORY
The historical nearest-first implementation below is diagnostic only. Sequential
effects are conditional on their order, not an order-independent causal proof.
"""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import shutil
from unittest.mock import patch

import geopandas as gpd
import numpy as np
import pandas as pd
import shapely
from shapely.geometry import box
from shapely.ops import transform

from region_mask import ocean_partition as op
from region_mask.oceans import generate_oceans
from .common import SIDECARS, environment, export_reference, sha256, write_json
from .geometry import AREA_METHOD, compare_geometry


def legacy_partition(ocean, marine):
    """Reproduce the former overlay + Mercator nearest-first gap assignment."""
    main = gpd.overlay(ocean[['geometry']], marine[['parent_reg','geometry']],
                       how='intersection', keep_geom_type=True)
    gaps = gpd.GeoDataFrame(geometry=ocean.geometry.difference(marine.union_all()), crs=ocean.crs)
    gaps = gaps.explode(index_parts=False)
    gaps = gaps[gaps.geom_type.isin(['Polygon','MultiPolygon'])].reset_index(drop=True)
    assigned = gpd.sjoin_nearest(gaps.to_crs(3857), marine[['parent_reg','geometry']].to_crs(3857), how='left')
    assigned = assigned[~assigned.index.duplicated(keep='first')]
    gaps['parent_reg'] = assigned.parent_reg
    combined = pd.concat([main,gaps],ignore_index=True)
    combined['parent_reg'] = combined.parent_reg.fillna('Unassigned Marine Area')
    return combined.dissolve(by='parent_reg',as_index=False)[['parent_reg','geometry']]


def prepared_marine(marine_path, ocean_path, codes_path, scratch):
    """Capture the production mapping/split without duplicating it or writing a product."""
    captured = {}
    class Captured(Exception):
        pass
    def capture(water, marine):
        captured['marine'] = marine.copy()
        raise Captured
    with patch('region_mask.oceans.ocean_domain', return_value=None), patch(
            'region_mask.oceans.partition_ocean', side_effect=capture):
        try:
            generate_oceans(marine_path,ocean_path,codes_path,scratch/'unused.shp')
        except Captured:
            pass
    return captured['marine']


def close_seam(marine):
    result=marine.copy()
    result.geometry=result.geometry.map(lambda g: op.polygonal(transform(
        lambda x,y,z=None: (np.where(np.asarray(x)>=179.9998,180.,x),y),g)))
    return result


def compare_frames(before, after):
    a,b=before.set_index('parent_reg'),after.set_index('parent_reg')
    if set(a.index)!=set(b.index):
        raise ValueError('Region membership changed during controlled experiment')
    return {name:compare_geometry(a.loc[name].geometry,b.loc[name].geometry) for name in sorted(a.index)}


def change_table(metrics):
    lines=['| Region | Added km² | Removed km² | Net km² | Changed km² | Numerical uncertainty km² |',
           '|---|---:|---:|---:|---:|---:|']
    for name,m in metrics.items():
        keys=['added_km2','removed_km2','net_transfer_km2','symmetric_difference_km2','change_numerical_uncertainty_km2']
        lines.append('| '+name+' | '+' | '.join(f'{m[k]:.9g}' if k in m else 'unavailable (invalid geometry)' for k in keys)+' |')
    return lines


def atlas(output, marine, baseline, final, gaps):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from matplotlib.patches import Patch
    names=sorted(final.parent_reg)
    colors=dict(zip(names,plt.get_cmap('tab20').colors[:len(names)]))
    locations=[{'bounds':op.GIBRALTAR_WINDOW,'labels':['North Atlantic Ocean','Mediterranean Region'], 'kind':'Gibraltar'}]+gaps
    pages=[]
    for number,location in enumerate(locations):
        bounds=location['bounds']; dx=max(.01,(bounds[2]-bounds[0])*.12); dy=max(.01,(bounds[3]-bounds[1])*.12)
        window=box(bounds[0]-dx,bounds[1]-dy,bounds[2]+dx,bounds[3]+dy)
        fig,axes=plt.subplots(1,4,figsize=(16,4),sharex=True,sharey=True)
        for ax,frame,title in zip(axes[:3],[marine,baseline,final],['Coarse source labels','Pinned baseline','Current corrected candidate']):
            for name in names:
                subset=frame[frame.parent_reg==name].copy()
                subset.geometry=subset.geometry.map(lambda g:op.polygonal(g.intersection(window)))
                subset=subset[~subset.is_empty]
                if len(subset):subset.plot(ax=ax,color=colors[name],edgecolor='black',linewidth=.15)
            ax.set_title(title,fontsize=10)
        changes=[]
        for name in names:
            a=op.polygonal(baseline.loc[baseline.parent_reg==name].geometry.iloc[0].intersection(window))
            b=op.polygonal(final.loc[final.parent_reg==name].geometry.iloc[0].intersection(window))
            changes.append(a.symmetric_difference(b))
        changed=op.polygonal(shapely.union_all(changes))
        if not changed.is_empty:gpd.GeoSeries([changed],crs=4326).plot(ax=axes[3],color='#cc0088',edgecolor='#cc0088',linewidth=.3)
        axes[3].set_title('Any label/footprint change (magenta)',fontsize=10)
        for ax in axes:
            ax.set_xlim(window.bounds[0],window.bounds[2]); ax.set_ylim(window.bounds[1],window.bounds[3])
            ax.set_facecolor('#eeeeee'); ax.tick_params(labelsize=7); ax.set_aspect('auto')
        present=marine[marine.intersects(window)]
        labels=sorted(set(present.parent_reg)|set(location['labels']))
        fig.legend(handles=[Patch(facecolor=colors[n],label=n) for n in labels],loc='lower center',ncol=2,fontsize=8)
        fig.suptitle(f'{number:02d}: {location["kind"]} — lon/lat bounds {tuple(round(x,5) for x in bounds)}',fontsize=10)
        fig.tight_layout(rect=(0,.13,1,.93))
        path=output/'figures'/f'{number:02d}.png';path.parent.mkdir(exist_ok=True)
        fig.savefig(path,dpi=140);plt.close(fig)
        pages.append({**location,'figure':str(path.relative_to(output)),
                      'source_names':sorted(set(present['name'])),'review_status':'unreviewed'})
        print(f'Atlas {number+1}/{len(locations)}',flush=True)
    return pages


def run(root, output):
    output.mkdir(parents=True,exist_ok=False)
    config=json.loads((root/'regression/baseline.json').read_text())
    paths=['data/oceans_from_ne_10m/oceans_from_ne_10m.shp','data/countries_from_ne_10m/countries_from_ne_10m.shp',
           'data/ne_10m/ne_10m_ocean/ne_10m_ocean.shp',
           'data/ne_10m/ne_10m_geography_marine_polys/ne_10m_geography_marine_polys.shp']
    blobs=[str(Path(p).with_suffix(s)) for p in paths for s in SIDECARS]+['data/codes_id.csv']
    commit=export_reference(root,config['reference_commit'],blobs,output/'reference')
    ref=output/'reference'
    sources={}
    for folder in ['region_mask','regression']:
        for src in sorted((root/folder).glob('*.py')):
            dst=output/'sources'/folder/src.name;dst.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(src,dst)
            sources[str(src.relative_to(root))]=sha256(dst)
    write_json(output/'manifest.json',{'reference_commit':commit,'sources':sources,'inputs':{p:sha256(ref/p) for p in blobs},'environment':environment()})
    baseline=gpd.read_file(ref/paths[0]).rename(columns={'NAME':'parent_reg'})[['parent_reg','geometry']]
    countries=gpd.read_file(ref/paths[1]);raw=gpd.read_file(ref/paths[2])
    marine=prepared_marine(ref/paths[3],ref/paths[2],ref/'data/codes_id.csv',output/'scratch')
    repaired=op.ocean_domain(raw)
    clipped=op.ocean_domain(raw,countries)
    def waterframe(w):return gpd.GeoDataFrame(geometry=[w],crs=4326)
    variants=[('00_baseline',baseline)]
    generators=[('01_legacy_rerun',lambda:legacy_partition(raw,marine)),
                ('02_explicit_water_repair',lambda:legacy_partition(waterframe(repaired),marine)),
                ('03_country_clipping',lambda:legacy_partition(waterframe(clipped),marine)),
                ('04_coarse_seam',lambda:legacy_partition(waterframe(clipped),close_seam(marine))),
                ('05_gap_inference',lambda:op.partition_ocean(clipped,marine,gibraltar=False))]
    stages={}
    for name,generate in generators:
        print('Generating '+name,flush=True)
        frame=generate();frame.to_file(output/f'{name}.gpkg',driver='GPKG')
        print('Measuring '+name,flush=True)
        stages[name]=compare_frames(variants[-1][1],frame)
        variants.append((name,frame));write_json(output/'stages.json',stages)
    gaps=[]; original=op._gap_pieces
    def record(gap,seeds,sample_metres):
        if len(seeds)>1:gaps.append({'bounds':list(gap.bounds),'labels':sorted(seeds),'kind':'Ambiguous gap'})
        return original(gap,seeds,sample_metres)
    print('Generating 06_gibraltar (full current method)',flush=True)
    with patch.object(op,'_gap_pieces',side_effect=record):
        final=op.partition_ocean(clipped,marine)
    final.to_file(output/'06_gibraltar.gpkg',driver='GPKG')
    stages['06_gibraltar']=compare_frames(variants[-1][1],final)
    total=compare_frames(baseline,final)
    write_json(output/'stages.json',stages);write_json(output/'total.json',total)
    pages=atlas(output,marine,baseline,final,gaps)
    write_json(output/'atlas.json',pages)
    lines=['# Controlled ocean correction review','',f'Reference: `{commit}`.','',
           'Production data and baseline are unchanged. This is a review experiment, not approval of any boundary.','',
           '## Measurement','',AREA_METHOD,'',
           'Net is added minus removed; changed is added plus removed. A transfer appears in both affected regions. '
           'Uncertainty does not include input-coordinate or geographical uncertainty. Exact geometry acceptance remains unchanged.','',
           '## Total versus pinned baseline','']+change_table(total)
    lines+=['','## Controlled sequence','',
            'Each table compares to the preceding stage, not directly to baseline. Effects depend on order and interact. '
            'Legacy rerun is a control for runtime/implementation differences. Explicit repair measures repair-policy differences '
            'beyond repairs already implicit in the historical overlay. Country clipping may also change nearest-first assignments '
            'through gap connectivity. Gap inference includes deterministic grouping and replacement of the old nearest-first policy. '
            'The last stage isolates Gibraltar including its interaction with gap inference.','']
    for name,metrics in stages.items():lines+=['### '+name,'']+change_table(metrics)+['']
    lines+=['## Review atlas','',
            'Axes are longitude/latitude, not an equal-area map. Grey means outside the displayed polygons, not necessarily land. '
            'Magenta includes label transfers and footprint differences. Fine slivers can be smaller than a pixel. '
            'All locations remain unapproved; inspect source names as well as geometry.','']
    for i,page in enumerate(pages):
        lines += [f'### {i:02d}: {page["kind"]}','',f'Bounds: `{page["bounds"]}`. Status: **unreviewed**.','',
                  'Coarse source names: '+', '.join(page['source_names'])+'.','',f'![Location {i:02d}]({page["figure"]})','']
    (output/'report.md').write_text('\n'.join(lines)+'\n')
    print('Review written to '+str(output/'report.md'),flush=True)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root',type=Path,default=Path.cwd())
    parser.add_argument('--output',type=Path,default=Path('regression-runs')/('ocean-review-'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S.%fZ')))
    args=parser.parse_args();run(args.root.resolve(),args.output.resolve())


if __name__=='__main__':main()
