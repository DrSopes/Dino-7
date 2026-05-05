#!/usr/bin/env python3
import argparse
import subprocess
import sys
import tempfile
from pathlib import Path

import gdstk


def run(cmd):
    subprocess.run(cmd, check=True)


def top_cell_from_lib(lib):
    tops = lib.top_level()
    if len(tops) == 1:
        return tops[0]
    if tops:
        return tops[0]
    if not lib.cells:
        raise RuntimeError('No hi ha cap cel·la dins del GDS')
    return lib.cells[0]


def find_cell(lib, requested=None):
    if requested:
        for cell in lib.cells:
            if cell.name == requested:
                return cell
        raise RuntimeError(f'No s\'ha trobat la cel·la {requested}')
    return top_cell_from_lib(lib)


def build_logo_from_png(png_path, output_gds, script_path, layer, datatype, threshold, pixel_size, target_width, offset_x, offset_y, cell_name):
    cmd = [
        sys.executable,
        script_path,
        '--input', png_path,
        '--output', output_gds,
        '--layer', str(layer),
        '--datatype', str(datatype),
        '--threshold', str(threshold),
        '--pixel-size', str(pixel_size),
        '--target-width', str(target_width),
        '--offset-x', str(offset_x),
        '--offset-y', str(offset_y),
        '--cell-name', cell_name,
    ]
    run(cmd)


def main():
    p = argparse.ArgumentParser(description='Fusiona un logo GDS dins del top GDS del projecte.')
    p.add_argument('--base-gds', required=True)
    p.add_argument('--output-gds', required=True)
    p.add_argument('--target-cell', required=True)
    p.add_argument('--logo-gds')
    p.add_argument('--logo-png')
    p.add_argument('--png-to-gds-script', default='logo.py')
    p.add_argument('--logo-cell', default='LOGO_MACRO')
    p.add_argument('--x', type=float, required=True)
    p.add_argument('--y', type=float, required=True)
    p.add_argument('--scale', type=float, default=1.0)
    p.add_argument('--rotation', type=float, default=0.0)
    p.add_argument('--flatten-logo', action='store_true')
    p.add_argument('--layer', type=int, default=81)
    p.add_argument('--datatype', type=int, default=0)
    p.add_argument('--threshold', type=int, default=128)
    p.add_argument('--pixel-size', type=float, default=0.4)
    p.add_argument('--target-width', type=int, default=200)
    p.add_argument('--offset-x', type=float, default=10.0)
    p.add_argument('--offset-y', type=float, default=10.0)
    args = p.parse_args()

    if not args.logo_gds and not args.logo_png:
        raise RuntimeError('Cal passar --logo-gds o --logo-png')

    with tempfile.TemporaryDirectory() as tmp:
        logo_gds_path = args.logo_gds
        if not logo_gds_path and args.logo_png:
            logo_gds_path = str(Path(tmp) / 'logo_from_png.gds')
            build_logo_from_png(
                png_path=args.logo_png,
                output_gds=logo_gds_path,
                script_path=args.png_to_gds_script,
                layer=args.layer,
                datatype=args.datatype,
                threshold=args.threshold,
                pixel_size=args.pixel_size,
                target_width=args.target_width,
                offset_x=args.offset_x,
                offset_y=args.offset_y,
                cell_name=args.logo_cell,
            )

        base_lib = gdstk.read_gds(args.base_gds)
        target_cell = find_cell(base_lib, args.target_cell)

        logo_lib = gdstk.read_gds(logo_gds_path)
        logo_cell = find_cell(logo_lib, args.logo_cell if args.logo_cell else None)

        existing_names = {c.name for c in base_lib.cells}
        imported_logo = logo_cell
        if logo_cell.name in existing_names:
            imported_logo = logo_cell.copy(logo_cell.name + '_imported')
        base_lib.add(imported_logo)

        ref = gdstk.Reference(
            imported_logo,
            origin=(args.x, args.y),
            rotation=args.rotation,
            magnification=args.scale,
        )

        if args.flatten_logo:
            target_cell.add(*ref.apply_repetition().get_polygons())
        else:
            target_cell.add(ref)

        Path(args.output_gds).parent.mkdir(parents=True, exist_ok=True)
        base_lib.write_gds(args.output_gds)
        print(f'GDS generat: {args.output_gds}')


if __name__ == '__main__':
    main()
