import os
import re
import shutil
from pathlib import Path
import ezdxf
import matplotlib.pyplot as plt
import matplotlib.patches as patches
from PIL import Image
from ezdxf.addons.drawing import RenderContext, Frontend
from ezdxf.addons.drawing.matplotlib import MatplotlibBackend
from ezdxf.addons.drawing.properties import LayoutProperties
from ezdxf.addons.drawing.config import Configuration

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
        if entity.dxftype() == "LWPOLYLINE":
            points = [(x, y) for x, y, *_ in entity.get_points()]
        else:
            points = [(x, y) for x, y, *_ in entity.points()]
        xs = [p[0] for p in points]
        ys = [p[1] for p in points]
        return min(xs), min(ys), max(xs), max(ys)
    except Exception:
        return None

def ponto_no_bbox(x, y, bbox, margem=1):
    x1, y1, x2, y2 = bbox
    return (x1 - margem <= x <= x2 + margem) and (y1 - margem <= y <= y2 + margem)

def centro_bbox(bbox):
    x1, y1, x2, y2 = bbox
    return (x1 + x2) / 2, (y1 + y2) / 2

def distancia(p1, p2):
    return ((p1[0]-p2[0])**2 + (p1[1]-p2[1])**2)**0.5

def is_quadrado(polyline):
    try:
        if polyline.dxftype() == "LWPOLYLINE":
            points = [(x, y) for x, y, *_ in polyline.get_points()]
        else:
            points = [(x, y) for x, y, *_ in polyline.points()]
        if len(points) != 4 or not polyline.closed:
            return False
        def dist(p1, p2):
            return ((p1[0]-p2[0])**2 + (p1[1]-p2[1])**2)**0.5
        lados = [dist(points[i], points[(i+1)%4]) for i in range(4)]
        media = sum(lados) / 4
        return all(abs(l - media) < 1.0 for l in lados)
    except Exception:
        return False

# =============================
# Processamento
# =============================
def filtrar_perfis(msp):
    perfis = []
    for e in msp.query('LWPOLYLINE POLYLINE'):
        perfis.append({
            "polyline": e,
            "texts": [],
            "dimensions": []
        })
    return perfis


def associar_entidades(msp, perfis):
    textos = [e for e in msp.query('TEXT MTEXT')]
    cotas = [e for e in msp.query('DIMENSION ROTATEDDIMENSION')]

    for perfil in perfis:
        bbox = get_bbox(perfil["polyline"])
        if not bbox:
            continue
        centro = centro_bbox(bbox)

        for t in textos:
            try:
                x, y, _ = t.dxf.insert
            except AttributeError:
                continue
            if ponto_no_bbox(x, y, bbox):
                conteudo = t.plain_text() if hasattr(t, "plain_text") else t.dxf.text
                perfil["texts"].append(conteudo)

        for d in cotas:
            try:
                x, y, _ = d.dxf.defpoint
            except AttributeError:
                continue
            if distancia((x, y), centro) < 100:
                perfil["dimensions"].append(d)

    return perfis

def extrair_nome(texts):
    for t in texts:
        if not re.search(r"Kg/m", t):
            return t.strip()
    return "perfil_sem_nome"

# =============================
# Renderização
# =============================
def render_completo(doc, ax):
    ctx = RenderContext(doc)

    layout_props = LayoutProperties.from_layout(doc.modelspace())
    layout_props.set_colors(bg="#FFFFFF", fg="#000000")  # fundo branco, tudo preto

    config = Configuration.defaults().with_changes(
        lineweight_scaling=3.0,
        min_lineweight=0.8
    )

    backend = MatplotlibBackend(ax)
    frontend = Frontend(ctx, backend, config=config)

    # Filtro: exclui textos e molduras
    def filtro(ent):
        tipo = ent.dxftype()
        camada = ent.dxf.layer.upper()
        return tipo not in ["TEXT", "MTEXT"] and camada != "MOLDURA"

    frontend.draw_layout(doc.modelspace(), finalize=True, layout_properties=layout_props, filter_func=filtro)



def render_imagens(doc, perfil, nome_base):
    nome = f"{nome_base}_com_cotas"

    if perfil["polyline"].dxftype() == "LWPOLYLINE":
        points = [(x, y) for x, y, *_ in perfil["polyline"].get_points()]
    else:
        points = [(x, y) for x, y, *_ in perfil["polyline"].points()]

    xs = [p[0] for p in points]
    ys = [p[1] for p in points]
    min_x, max_x = min(xs), max(xs)
    min_y, max_y = min(ys), max(ys)
    margem = 10

    lim_x1 = min_x - margem
    lim_x2 = max_x + margem
    lim_y1 = min_y - margem
    lim_y2 = max_y + margem

    # PNG com cotas — renderiza normalmente
    fig, ax = plt.subplots(figsize=(5, 5), dpi=100)
    ax.set_facecolor("#FFFFFF")
    ax.set_axis_off()
    ax.set_position([0, 0, 1, 1])
    ax.set_xlim(lim_x1, lim_x2)
    ax.set_ylim(lim_y1, lim_y2)
    ax.set_aspect('equal')

    polygon = patches.Polygon(points, closed=True, facecolor="#000000", edgecolor="#000000", linewidth=1.5)
    ax.add_patch(polygon)
    render_completo(doc, ax)

    temp_png = FIGURAS_DIR / f"{nome}_temp.png"
    fig.savefig(temp_png, dpi=100, transparent=False)
    plt.close(fig)

    # Redimensiona para 500x500 com PIL
    with Image.open(temp_png) as img:
        resized = img.resize((500, 500), Image.LANCZOS)
        path_png = FIGURAS_DIR / f"{nome}.png"
        resized.save(path_png)
    temp_png.unlink()

    # BMP sem cotas — 64x64
    fig, ax = plt.subplots(figsize=(0.64, 0.64), dpi=100)
    ax.set_facecolor("#FFFFFF")
    ax.set_axis_off()
    ax.set_position([0, 0, 1, 1])
    ax.set_xlim(lim_x1, lim_x2)
    ax.set_ylim(lim_y1, lim_y2)
    ax.set_aspect('equal')

    polygon_icon = patches.Polygon(points, closed=True, facecolor="#000000", edgecolor="#000000", linewidth=1.5)
    ax.add_patch(polygon_icon)

    temp_icon_png = ICONES_DIR / f"{nome_base}_temp.png"
    fig.savefig(temp_icon_png, dpi=100, transparent=False)
    plt.close(fig)

    with Image.open(temp_icon_png) as img:
        resized_icon = img.resize((64, 64), Image.LANCZOS)
        path_bmp = ICONES_DIR / f"{nome_base}.bmp"
        resized_icon.save(path_bmp, format="BMP")
    


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
def main():
    if OUTPUT_DIR.exists():
        shutil.rmtree(OUTPUT_DIR)
    FIGURAS_DIR.mkdir(parents=True, exist_ok=True)
    ICONES_DIR.mkdir(parents=True, exist_ok=True)

    input_file = Path("files") / "Perfis.dxf"
    doc, msp = carregar_dxf(input_file)
    perfis = filtrar_perfis(msp)
    perfis = associar_entidades(msp, perfis)

    for i, perfil in enumerate(perfis):
        nome_base = extrair_nome(perfil["texts"])
        render_imagens(doc, perfil, f"{nome_base}_{i}")

    compactar_output()
    print(f"✅ Imagens geradas com cotas (PNG) e sem cotas (BMP). Arquivo final: {ZIP_PATH}")

if __name__ == "__main__":
    main()
