import os
import re
import shutil
from pathlib import Path
import ezdxf
from ezdxf.addons.drawing import RenderContext, Frontend
from ezdxf.addons.drawing.matplotlib import MatplotlibBackend
import matplotlib.pyplot as plt
from PIL import Image

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

def ponto_no_bbox(x, y, bbox, margem=5):
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
    cotas = [e for e in msp.query('DIMENSION ROTATEDDIMENSION')]

    for perfil in perfis:
        bbox = get_bbox(perfil["polyline"])
        if not bbox:
            continue

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
            if ponto_no_bbox(x, y, bbox, margem=20):
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

def render_dxf_to_image(doc, path, size=(500, 500), bg_color="#073484"):
    fig = plt.figure(figsize=(size[0]/100, size[1]/100), dpi=100)
    ax = fig.add_axes([0, 0, 1, 1])
    ax.set_facecolor(bg_color)
    ax.set_axis_off()

    ctx = RenderContext(doc)
    out = MatplotlibBackend(ax)
    Frontend(ctx, out).draw_layout(doc.modelspace(), finalize=True)

    fig.savefig(path, dpi=100, transparent=False)
    plt.close(fig)

def render_imagens(perfil, nome):
    # -----------------------------
    # PNG 500x500
    # -----------------------------
    doc_fig = ezdxf.new()
    msp_fig = doc_fig.modelspace()

    # Adiciona polyline com cor preta
    if perfil["polyline"].dxftype() == "LWPOLYLINE":
        points = perfil["polyline"].get_points()
        msp_fig.add_lwpolyline(points, dxfattribs={'color': 0})  # 0 = preto
    else:
        msp_fig.add_polyline2d(perfil["polyline"].points(), dxfattribs={'color': 0})

    # Adiciona cotas
    for d in perfil["dimensions"]:
        try:
            msp_fig.add_entity(d.copy())
        except Exception:
            pass

    path_png = FIGURAS_DIR / f"{nome}.png"
    render_dxf_to_image(doc_fig, path_png, size=(500, 500), bg_color="#4E5480")

    # -----------------------------
    # BMP 64x64
    # -----------------------------
    doc_icon = ezdxf.new()
    msp_icon = doc_icon.modelspace()
    if perfil["polyline"].dxftype() == "LWPOLYLINE":
        points = perfil["polyline"].get_points()
        msp_icon.add_lwpolyline(points, dxfattribs={'color': 0})
    else:
        msp_icon.add_polyline2d(perfil["polyline"].points(), dxfattribs={'color': 0})

    temp_icon_png = ICONES_DIR / f"{nome}_temp.png"
    render_dxf_to_image(doc_icon, temp_icon_png, size=(64, 64), bg_color="#FFFFFF")

    img = Image.open(temp_icon_png)
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
