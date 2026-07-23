import sys
import time
import shutil
from pathlib import Path
from SICAR import Sicar, Polygon
import argparse

LAYER_OPTIONS = {
    "property": (Polygon.AREA_PROPERTY, "area_overlay"),
    "app": (Polygon.APPS, "app_overlay"),
    "vegetation": (Polygon.NATIVE_VEGETATION, "native_vegetation_overlay"),
    "reserve": (Polygon.LEGAL_RESERVE, "legal_reserve_overlay"),
    "consolidated": (Polygon.CONSOLIDATED_AREA, "consolidated_area_overlay"),
    "hydrography": (Polygon.HYDROGRAPHY, "hydrography_overlay"),
    "fallow": (Polygon.AREA_FALL, "fallow_overlay"),
    "restricted": (Polygon.RESTRICTED_USE, "restricted_use_overlay"),
    "administrative": (
        Polygon.ADMINISTRATIVE_SERVICE,
        "administrative_service_overlay",
    ),
}


class CARDownloader:
    def __init__(self, output_dir="source"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.car = Sicar()

    def organize_downloaded_files(self, state):
        actual_directory = Path(".")
        files_found = list(actual_directory.rglob(f"*{state.name}*.zip"))
        valid_files = [f for f in files_found if self.output_dir not in f.parents]

        if valid_files:
            for origin_file in valid_files:
                target_file = self.output_dir / origin_file.name
                shutil.move(str(origin_file), str(target_file))
            return True
        return False


def run(
    target_polygon=Polygon.AREA_PROPERTY,
    overlay_name="area_overlay",
    target_state=None,
):
    SOURCE_FOLDER = Path("source") / overlay_name

    print("=" * 60)
    print(f"   DOWNLOADER SICAR: {overlay_name.upper()} ")
    print("=" * 60)

    downloader = None
    for tentativa in range(1, 6):
        try:
            downloader = CARDownloader(output_dir=SOURCE_FOLDER)
            break
        except Exception as e:
            if tentativa < 5:
                time.sleep(15)
            else:
                sys.exit(1)

    try:
        state_dates = downloader.car.get_release_dates()
    except Exception as e:
        print("ERROR: {e}", err=True)
        sys.exit(1)

    for state in state_dates.keys():
        uf = state.name

        if target_state and uf != target_state.upper():
            continue

        print(f">>> Baixando {uf} para a camada: {overlay_name}")

        try:
            downloader.car.download_state(state, target_polygon)
            downloader.organize_downloaded_files(state)
            print(f"Sucesso: {uf} baixado e organizado.")
        except Exception as e:
            print(f"ERROR: Falha ao baixar {uf}: {e}", err=True)

        time.sleep(5)

    print(f"\nSUCESSO: DOWNLOAD PARA {overlay_name.upper()} FINALIZADO!")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Downloader isolado de ZIPs do SICAR.")
    parser.add_argument(
        "--layer",
        choices=list(LAYER_OPTIONS.keys()) + ["all"],
        default="property",
        help="Escolha qual camada do SICAR deseja baixar, ou 'all' para todas (padrão: property)",
    )
    parser.add_argument(
        "--state",
        default=None,
        help="Sigla de um estado específico (ex: AC, SP, MT). Se vazio, baixa todos.",
    )

    args = parser.parse_args()

    layers_to_run = LAYER_OPTIONS.keys() if args.layer == "all" else [args.layer]

    for layer_key in layers_to_run:
        target_polygon, overlay_name = LAYER_OPTIONS[layer_key]
        run(
            target_polygon=target_polygon,
            overlay_name=overlay_name,
            target_state=args.state,
        )
