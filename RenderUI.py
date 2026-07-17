# =============================
# Imports
# =============================
import re
import ezdxf
import shutil
import threading
import tkinter as tk
from PIL import Image
from pathlib import Path
import matplotlib.pyplot as plt
import matplotlib.patches as patches
from ezdxf import path as ezdxf_path
from tkinter import filedialog, messagebox
from ezdxf.addons.drawing.config import Configuration
from ezdxf.addons.drawing import RenderContext, Frontend
from ezdxf.addons.drawing.matplotlib import MatplotlibBackend
from ezdxf.addons.drawing.properties import LayoutProperties

# =============================
# Configurações de diretórios
# =============================


OUTPUT_DIR = Path("./output")
TMP_DIR = OUTPUT_DIR / "tmp"
FIGURAS_DIR = TMP_DIR / "figuras"
ICONES_DIR = TMP_DIR / "icones"
ZIP_PATH = OUTPUT_DIR / "imagens.zip"
CURVE_FLATTENING_DISTANCE = 0.5
TEXT_ASSOCIATION_MARGIN = 30


# =============================
# Utilidades
# =============================


def carregar_dxf(path: str):
    doc = ezdxf.readfile(path)
    msp = doc.modelspace()
    return doc, msp


def sanitize_filename(name: str) -> str:
    name = name.replace("\n", "_").replace("\r", "_")
    name = name.replace("\\", "_").replace("/", "_")
    name = re.sub(r'[^a-zA-Z0-9._-]', "_", name)
    return name


def limpar_pontos_repetidos(points):
    limpos = []
    for ponto in points:
        if not limpos or distancia(limpos[-1], ponto) > 1e-9:
            limpos.append(ponto)
    if len(limpos) > 1 and distancia(limpos[0], limpos[-1]) <= 1e-9:
        limpos.pop()
    return limpos


def entity_to_points(entity, distance=CURVE_FLATTENING_DISTANCE):
    """Converte linhas, polilinhas com bulge e curvas DXF em pontos 2D."""
    try:
        dxf_path = ezdxf_path.make_path(entity)
        points = [(p.x, p.y) for p in dxf_path.flattening(distance=distance, segments=16)]
        points = limpar_pontos_repetidos(points)
        if len(points) >= 2:
            return points
    except Exception:
        pass

    try:
        if hasattr(entity, "virtual_entities"):
            points = []
            for virtual_entity in entity.virtual_entities():
                virtual_points = entity_to_points(virtual_entity, distance=distance)
                points.extend(virtual_points)
            points = limpar_pontos_repetidos(points)
            if len(points) >= 2:
                return points
    except Exception:
        pass

    try:
        if entity.dxftype() == "LWPOLYLINE":
            return [(x, y) for x, y, *_ in entity.get_points()]
        return [(x, y) for x, y, *_ in entity.points()]
    except Exception:
        return []


def is_closed_geometry(entity):
    if entity.dxftype() in {"CIRCLE", "ELLIPSE"}:
        return True
    return bool(getattr(entity, "closed", False))


def get_bbox(entity):
    try:
        points = entity_to_points(entity)
        if not points:
            return None
        xs = [p[0] for p in points]
        ys = [p[1] for p in points]
        return min(xs), min(ys), max(xs), max(ys)
    except Exception:
        return None


def polygon_area(points):
    if len(points) < 3:
        return 0
    area = 0
    for i, ponto in enumerate(points):
        proximo = points[(i + 1) % len(points)]
        area += ponto[0] * proximo[1] - proximo[0] * ponto[1]
    return abs(area) / 2


def entity_area(entity):
    return polygon_area(entity_to_points(entity))


def ponto_no_bbox(x, y, bbox, margem=15):
    x1, y1, x2, y2 = bbox
    return (x1 - margem <= x <= x2 + margem) and (y1 - margem <= y <= y2 + margem)


def centro_bbox(bbox):
    x1, y1, x2, y2 = bbox
    return (x1 + x2) / 2, (y1 + y2) / 2


def distancia(p1, p2):
    return ((p1[0] - p2[0])**2 + (p1[1] - p2[1])**2)**0.5


def is_quadrado(polyline):
    try:
        points = entity_to_points(polyline)
        if len(points) != 4 or not is_closed_geometry(polyline):
            return False

        def dist(p1, p2):
            return ((p1[0] - p2[0])**2 + (p1[1] - p2[1])**2)**0.5
        lados = [dist(points[i], points[(i + 1) % 4]) for i in range(4)]
        media = sum(lados) / 4
        return all(abs(l - media) < 1.0 for l in lados)

    except Exception:
        return False


def centralizar_em_moldura(img_path, tamanho_final=(500, 500)):
    with Image.open(img_path) as img:
        img = img.convert("RGBA")
        img.thumbnail(tamanho_final, Image.Resampling.LANCZOS)

        fundo = Image.new("RGBA", tamanho_final, (255, 255, 255, 255))
        x = (tamanho_final[0] - img.width) // 2
        y = (tamanho_final[1] - img.height) // 2

        fundo.paste(img, (x, y), img)
        fundo = fundo.convert("RGB")
        fundo.save(img_path)


def detectar_furos(msp, perfis):
    candidatos = [e for e in msp.query('LWPOLYLINE POLYLINE CIRCLE ELLIPSE') if is_closed_geometry(e)]

    for perfil in perfis:
        principal = perfil["polyline"]
        bbox_principal = get_bbox(principal)

        if not bbox_principal:
            continue

        for furo in candidatos:
            if furo == principal:
                continue
            bbox_furo = get_bbox(furo)
            if not bbox_furo:
                continue
            centro_furo = centro_bbox(bbox_furo)
            if ponto_no_bbox(centro_furo[0], centro_furo[1], bbox_principal, margem=2):
                perfil["furos"].append(furo)


# =============================
# Processamento
# =============================


def filtrar_perfis(msp):
    candidatos = []
    for e in msp.query('LWPOLYLINE POLYLINE'):
        if e.dxf.layer.upper() == "MOLDURA":
            continue
        bbox = get_bbox(e)
        if not bbox:
            continue
        candidatos.append({
            "entity": e,
            "bbox": bbox,
            "centro": centro_bbox(bbox),
            "area": entity_area(e),
        })

    perfis = []
    for candidato in candidatos:
        centro = candidato["centro"]
        area = candidato["area"]
        esta_contido = any(
            outro is not candidato
            and outro["area"] > area
            and ponto_no_bbox(centro[0], centro[1], outro["bbox"], margem=0)
            for outro in candidatos
        )
        if esta_contido:
            continue

        e = candidato["entity"]
        perfis.append({
            "polyline": e,
            "texts": [],
            "dimensions": [],
            "furos": []
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
            if ponto_no_bbox(x, y, bbox, margem=TEXT_ASSOCIATION_MARGIN):
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
        nome = re.sub(r"\s*\d+[,\.]?\d*\s*kg/m", "", t, flags=re.IGNORECASE)
        nome = nome.strip()
        if nome:
            return sanitize_filename(nome)
    return "perfil_sem_nome"


def nome_unico(nome_base, nomes_usados):
    nome = sanitize_filename(nome_base.strip()) if nome_base.strip() else "perfil_sem_nome"
    quantidade = nomes_usados.get(nome, 0) + 1
    nomes_usados[nome] = quantidade
    if quantidade == 1:
        return nome
    return f"{nome}_{quantidade}"


# =============================
# Renderização
# =============================


def desenhar_perfil_com_furos(ax, perfil, facecolor="#000000", edgecolor="#000000", furo_color="#FFFFFF", linewidth=1.5):
    """Desenha o perfil principal e seus furos em um eixo Matplotlib."""
    pontos_principais = entity_to_points(perfil["polyline"])
    if not pontos_principais:
        return

    poly_patch = patches.Polygon(pontos_principais, closed=True, facecolor=facecolor, edgecolor=edgecolor, linewidth=linewidth)
    ax.add_patch(poly_patch)

    for furo in perfil["furos"]:
        pontos = entity_to_points(furo)
        if not pontos:
            continue

        furo_patch = patches.Polygon(pontos, closed=True, facecolor=furo_color, edgecolor=edgecolor, linewidth=1.0)
        ax.add_patch(furo_patch)


def criar_layout_temporario(doc, perfil):
    layout_name = "TEMP_LAYOUT"
    if layout_name in doc.layouts:
        doc.layouts.delete(layout_name)
    layout = doc.layouts.new(layout_name)
    for entidade in [perfil["polyline"]] + perfil["dimensions"]:
        layout.add_entity(entidade.copy())
    return layout


def render_completo_layout(layout, ax):
    ctx = RenderContext(layout.doc)
    layout_props = LayoutProperties.from_layout(layout)
    layout_props.set_colors(bg="#FFFFFF", fg="#000000")
    config = Configuration.defaults().with_changes(
        lineweight_scaling=3.0,
        min_lineweight=0.8
    )
    backend = MatplotlibBackend(ax)
    frontend = Frontend(ctx, backend, config=config)
    frontend.draw_layout(layout, finalize=True, layout_properties=layout_props)


def render_imagens(doc, perfil, nome_base):
    nome = f"{nome_base}"

    points = entity_to_points(perfil["polyline"])
    if not points:
        return
    xs = [p[0] for p in points]
    ys = [p[1] for p in points]
    min_x, max_x = min(xs), max(xs)
    min_y, max_y = min(ys), max(ys)
    margem = 10

    # PNG com cotas
    fig, ax = plt.subplots(figsize=(5, 5), dpi=100)
    ax.set_facecolor("#FFFFFF")
    ax.set_axis_off()

    centro_x = (min_x + max_x) / 2
    centro_y = (min_y + max_y) / 2
    half_range = 50
    ax.set_xlim(centro_x - half_range, centro_x + half_range)
    ax.set_ylim(centro_y - half_range, centro_y + half_range)
    ax.set_aspect('equal')

    desenhar_perfil_com_furos(ax, perfil)
    layout_temp = criar_layout_temporario(doc, perfil)
    render_completo_layout(layout_temp, ax)

    path_png = FIGURAS_DIR / f"{nome}.png"
    fig.savefig(path_png, dpi=100, transparent=False)
    centralizar_em_moldura(path_png)
    plt.close(fig)

    # BMP sem cotas
    fig, ax = plt.subplots(figsize=(0.64, 0.64), dpi=100)
    ax.set_facecolor("#FFFFFF")
    ax.set_axis_off()

    desenhar_perfil_com_furos(ax, perfil)
    ax.set_xlim(min_x - margem, max_x + margem)
    ax.set_ylim(min_y - margem, max_y + margem)
    ax.set_aspect('equal')

    temp_icon_png = ICONES_DIR / f"{nome_base}_temp.png"
    fig.savefig(temp_icon_png, dpi=100, transparent=False)
    plt.close(fig)

    with Image.open(temp_icon_png) as img:
        path_bmp = ICONES_DIR / f"{nome_base}.bmp"
        img.save(path_bmp, format="BMP")
    temp_icon_png.unlink()


# =============================
# Exportação
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
# Função principal com caminhos
# =============================


def main_with_paths(input_path: Path, output_path: Path):
    # --- Preparação de diretórios ---
    TMP_DIR.mkdir(parents=True, exist_ok=True)
    FIGURAS_DIR.mkdir(parents=True, exist_ok=True)
    ICONES_DIR.mkdir(parents=True, exist_ok=True)
    output_path.mkdir(parents=True, exist_ok=True)

    # --- Carregar arquivo ---
    doc, msp = carregar_dxf(input_path)

    # --- Detectar perfis ---
    perfis = filtrar_perfis(msp)
    perfis = associar_entidades(msp, perfis)
    detectar_furos(msp, perfis)

    # --- Renderizar cada perfil ---
    nomes_usados = {}
    for perfil in perfis:
        nome = extrair_nome(perfil["texts"])
        render_imagens(doc, perfil, nome_unico(nome, nomes_usados))

    # --- Compactar resultados ---
    compactar_output()

    # --- Copiar ZIP para destino ---
    destino_zip = output_path / ZIP_PATH.name
    shutil.copy2(ZIP_PATH, destino_zip)

        # --- Remover arquivos temporários ---
    if TMP_DIR.exists():
        shutil.rmtree(TMP_DIR)

    print(f"✅ Renderização concluída. Arquivos salvos em: {destino_zip}")


# =============================
# Tkinter Interface Visual
# =============================


def escolher_input():
    caminho = filedialog.askopenfilename(filetypes=[("Arquivos DXF", "*.dxf")])
    if caminho:
        input_var.set(caminho)


def escolher_output():
    caminho = filedialog.askdirectory()
    if caminho:
        output_var.set(caminho)


def rodar_processo():
    input_path = Path(input_var.get())
    output_path = Path(output_var.get() or "./output")

    if not input_path.exists():
        messagebox.showerror("Erro", "Arquivo DXF inválido.")
        return

    def processar():
        try:
            messagebox.showinfo("Processando", "Renderização iniciada...")
            main_with_paths(input_path, output_path)
            messagebox.showinfo("Concluído", f"Imagens geradas em: {output_path}")
        except Exception as e:
            messagebox.showerror("Erro", str(e))

    # roda o processamento em thread separada para não travar o Tkinter
    threading.Thread(target=processar).start()


def iniciar_interface():
    global input_var, output_var

    root = tk.Tk()
    root.title("Renderizador DXF")
    root.geometry("500x250")

    input_var = tk.StringVar()
    output_var = tk.StringVar()

    # Input DXF
    tk.Label(root, text="Arquivo DXF:").pack(anchor="w", padx=10, pady=(10, 0))
    frame_input = tk.Frame(root)
    frame_input.pack(fill="x", padx=10)
    tk.Entry(frame_input, textvariable=input_var, width=50).pack(side="left", fill="x", expand=True)
    tk.Button(frame_input, text="Selecionar...", command=escolher_input).pack(side="right", padx=5)

    # Output
    tk.Label(root, text="Diretório de saída:").pack(anchor="w", padx=10, pady=(10, 0))
    frame_output = tk.Frame(root)
    frame_output.pack(fill="x", padx=10)
    tk.Entry(frame_output, textvariable=output_var, width=50).pack(side="left", fill="x", expand=True)
    tk.Button(frame_output, text="Selecionar...", command=escolher_output).pack(side="right", padx=5)

    # Executar
    tk.Button(root, text="Executar", command=rodar_processo, bg="#0078D7", fg="white").pack(pady=20)

    root.mainloop()


# =============================
# Execução principal (interface)
# =============================


if __name__ == "__main__":
    iniciar_interface()
