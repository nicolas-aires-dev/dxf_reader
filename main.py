import os
import re
import shutil
from pathlib import Path
import ezdxf
import matplotlib.pyplot as plt
import matplotlib.patches as patches
from PIL import Image
from ezdxf.entities import Dimension


# =============================
# Config
# =============================
OUTPUT_DIR = Path("./output")
TMP_DIR = OUTPUT_DIR / "tmp"
FIGURAS_DIR = TMP_DIR / "figuras"
ICONES_DIR = TMP_DIR / "icones"
ZIP_PATH = OUTPUT_DIR / "imagens.zip"


# =============================
# Utilidades
# =============================
def carregar_dxf(path: str):
    doc = ezdxf.readfile(path)
    msp = doc.modelspace()
    return doc, msp

def get_bbox(entity):
    try:
        ext = entity.bbox()
        (x1, y1, _), (x2, y2, _) = ext
        return x1, y1, x2, y2
    except Exception:
        return None

def ponto_no_bbox(x, y, bbox, margem=200):
    x1, y1, x2, y2 = bbox
    return (x1 - margem <= x <= x2 + margem) and (y1 - margem <= y <= y2 + margem)


# =============================
# Processamento
# =============================
def filtrar_perfis(msp):
    perfis = []
    for e in msp.query('*[layer=="PERFIS"]'):
        if e.dxftype() in ["LWPOLYLINE", "POLYLINE"]:
            perfis.append({
                "polyline": e,
                "texts": [],
                "dimensions": []
            })
    return perfis

def associar_entidades(msp, perfis):
    textos = [e for e in msp.query('TEXT MTEXT')]

    for perfil in perfis:
        bbox = get_bbox(perfil["polyline"])
        if not bbox:
            continue

        # textos soltos dentro do bbox
        for t in textos:
            try:
                x, y, _ = t.dxf.insert
            except AttributeError:
                continue
            if ponto_no_bbox(x, y, bbox):
                conteudo = t.plain_text() if hasattr(t, "plain_text") else t.dxf.text
                perfil["texts"].append(conteudo)

        # cotas renderizadas (entidades do bloco)
        for d in msp.query("DIMENSION"):
            try:
                block = d.get_block()
                if block is None:
                    continue
                for e in block:
                    if e.dxftype() in ("TEXT", "MTEXT"):
                        x, y, _ = e.dxf.insert
                        if ponto_no_bbox(x, y, bbox, margem=20):
                            perfil["dimensions"].append(e)
                    elif e.dxftype() in ("LINE", "ARC"):
                        perfil["dimensions"].append(e)
            except Exception as ex:
                print(f"⚠️ Erro ao processar bloco de cota: {ex}")

    return perfis

def extrair_nome(texts):
    for t in texts:
        if not re.search(r"Kg/m", t):
            return t.strip()
    return "perfil_sem_nome"

def renderizar_cotas(msp):
    """Força a renderização das entidades de cota (DIMENSION)."""
    for e in msp.query("DIMENSION"):
        try:
            e.render()  # sem discard
        except Exception as err:
            print(f"⚠️ Não consegui renderizar uma cota: {err}")


# =============================
# Renderização
# =============================
def render_imagens(perfil, nome):
    # -----------------------------
    # PNG 500x500 com preenchimento e cotas
    # -----------------------------
    if perfil["polyline"].dxftype() == "LWPOLYLINE":
        points = [(x, y) for x, y, *_ in perfil["polyline"].get_points()]
    else:
        points = [(x, y) for x, y, *_ in perfil["polyline"].points()]

    fig, ax = plt.subplots(figsize=(5, 5), dpi=100)
    ax.set_facecolor("#FFFFFF")
    ax.set_axis_off()

    # perfil preto preenchido
    polygon = patches.Polygon(points, closed=True, facecolor="#000000", edgecolor="#000000")
    ax.add_patch(polygon)

    # cotas renderizadas (TEXT, MTEXT, LINE, ARC)
    for e in perfil["dimensions"]:
        try:
            if e.dxftype() == "TEXT":
                x, y, _ = e.dxf.insert
                ax.text(x, y, e.dxf.text, color="black", fontsize=8,
                        ha="center", va="center")
            elif e.dxftype() == "MTEXT":
                x, y, _ = e.dxf.insert
                ax.text(x, y, e.text, color="black", fontsize=8,
                        ha="center", va="center")
            elif e.dxftype() == "LINE":
                x1, y1, _ = e.dxf.start
                x2, y2, _ = e.dxf.end
                ax.plot([x1, x2], [y1, y2], color="black", linewidth=0.5)
            elif e.dxftype() == "ARC":
                center = e.dxf.center
                radius = e.dxf.radius
                start_angle = e.dxf.start_angle
                end_angle = e.dxf.end_angle
                arc = patches.Arc(
                    (center[0], center[1]),
                    2*radius, 2*radius,
                    angle=0,
                    theta1=start_angle,
                    theta2=end_angle,
                    color="black", linewidth=0.5
                )
                ax.add_patch(arc)
        except Exception as ex:
            print(f"⚠️ Erro ao desenhar entidade de cota: {ex}")

    ax.autoscale_view()
    ax.set_aspect('equal')
    path_png = FIGURAS_DIR / f"{nome}.png"
    fig.savefig(path_png, dpi=100, transparent=False)
    plt.close(fig)

    # -----------------------------
    # BMP 64x64 simples (sem cotas)
    # -----------------------------
    fig, ax = plt.subplots(figsize=(0.64, 0.64), dpi=100)
    ax.set_facecolor("#FFFFFF")
    ax.set_axis_off()
    polygon_icon = patches.Polygon(points, closed=True, facecolor="#000000", edgecolor="#000000")
    ax.add_patch(polygon_icon)
    ax.autoscale_view()
    ax.set_aspect('equal')

    temp_icon_png = ICONES_DIR / f"{nome}_temp.png"
    fig.savefig(temp_icon_png, dpi=100, transparent=False)
    plt.close(fig)

    with Image.open(temp_icon_png) as img:
        path_bmp = ICONES_DIR / f"{nome}.bmp"
        img.save(path_bmp, format="BMP")
    temp_icon_png.unlink()


# =============================
# Export
# =============================
def compactar_output():
    if ZIP_PATH.exists():
        ZIP_PATH.unlink()
    shutil.make_archive(
        base_name=str(ZIP_PATH).replace(".zip", ""),
        format="zip",
        root_dir=TMP_DIR
    )


# =============================
# Main
# =============================
def main(input_dxf: str):
    if OUTPUT_DIR.exists():
        shutil.rmtree(OUTPUT_DIR)
    FIGURAS_DIR.mkdir(parents=True, exist_ok=True)
    ICONES_DIR.mkdir(parents=True, exist_ok=True)

    doc, msp = carregar_dxf(input_dxf)

    # 🔑 renderiza cotas primeiro
    renderizar_cotas(msp)

    perfis = filtrar_perfis(msp)
    perfis = associar_entidades(msp, perfis)

    for perfil in perfis:
        nome = extrair_nome(perfil["texts"])
        render_imagens(perfil, nome)

    compactar_output()
    print(f"✅ Arquivo final gerado em: {ZIP_PATH}")


if __name__ == "__main__":
    input_file = Path("files") / "Perfis.dxf"
    main(str(input_file))
