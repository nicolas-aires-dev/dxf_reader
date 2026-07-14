import ezdxf
from pathlib import Path


def criar_cotas_bbox(msp, polyline):
    try:
        bbox = polyline.bbox()
        (x1, y1, _), (x2, y2, _) = bbox
    except Exception:
        return

    # Cota horizontal (largura)
    largura = msp.add_rotated_dim(
        base=(x1, y1 - 5),
        p1=(x1, y1),
        p2=(x2, y1),
        angle=0,
        dimstyle='Standard',
        dxfattribs={'layer': 'PERFIS', 'color': 256}
    )
    largura.render()

    # Cota vertical (altura)
    altura = msp.add_rotated_dim(
        base=(x2 + 5, y1),
        p1=(x2, y1),
        p2=(x2, y2),
        angle=90,
        dimstyle='Standard',
        dxfattribs={'layer': 'PERFIS', 'color': 256}
    )
    altura.render()


def converter_blocos_para_polylines(input_path: str, output_path: str):
    doc = ezdxf.readfile(input_path)
    msp = doc.modelspace()

    # Cria layer PERFIS se não existir
    if "PERFIS" not in doc.layers:
        doc.layers.add("PERFIS", color=7)

    # Remove cotas antigas
    for dim in msp.query("DIMENSION"):
        msp.delete_entity(dim)

    # Explode blocos e converte para polylines
    inserts = list(msp.query("INSERT"))
    print(f"🔍 Encontrados {len(inserts)} blocos para conversão.")

    for insert in inserts:
        try:
            exploded = insert.explode()
            for e in exploded:
                if e.dxftype() in ["POLYLINE", "LWPOLYLINE"]:
                    e_copy = e.copy()
                    e_copy.dxf.layer = "PERFIS"
                    e_copy.dxf.color = 256
                    msp.add_entity(e_copy)
                    criar_cotas_bbox(msp, e_copy)
            msp.delete_entity(insert)
        except Exception as err:
            print(f"⚠️ Erro ao explodir bloco: {err}")

    if doc is not None:
        doc.saveas(output_path)
        print(f"✅ Arquivo convertido salvo em: {output_path}")
    else:
        print("Falha ao carregar o DXF.")


if __name__ == "__main__":
    input_file = Path("files") / "TestePreenchimento.dxf"
    output_file = Path("output") / "TestePreenchimento_convertido.dxf"
    converter_blocos_para_polylines(input_file, output_file)
