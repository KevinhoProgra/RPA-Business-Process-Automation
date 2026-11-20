"""
Generador de facturas PDF sintéticas para el proyecto RPA Invoice Processing.

Crea 44 PDFs en la carpeta ./Entrada con datos 100% ficticios, mezclando
facturas válidas con casos de error a propósito (duplicados, campos vacíos,
totales que no cuadran, fechas inválidas, proveedores inactivos/inexistentes).

También genera ./manifiesto_esperado.csv con el resultado que debería dar el
robot para cada archivo, para poder comprobar que las validaciones funcionan.

Uso:
    pip install reportlab
    python generar_facturas.py
"""

import csv
import itertools
import random
from datetime import date, timedelta
from pathlib import Path

from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas

SEED = 42
CARPETA_SALIDA = Path("Entrada")
MANIFIESTO = Path("manifiesto_esperado.csv")

# Proveedores que existen y están activos en la tabla dbo.Proveedores
PROVEEDORES = [
    ("Suministros del Norte SA de CV", "SNO010101AB1"),
    ("Papelería Central SA de CV", "PCE020202CD2"),
    ("Tecnología Integral SA de CV", "TIN030303EF3"),
    ("Servicios Logísticos MX SA de CV", "SLM040404GH4"),
]
# Existe en la BD pero con activo = 0
PROVEEDOR_INACTIVO = ("Mantenimiento Express SA de CV", "MEX050505IJ5")
# No existe en la BD
PROVEEDOR_DESCONOCIDO = ("Proveedor Fantasma SA de CV", "FAN999999ZZ9")

CONCEPTOS = [
    "Material de oficina",
    "Servicio de mantenimiento",
    "Licencias de software",
    "Transporte de mercancía",
    "Equipo de cómputo",
]

contador_facturas = itertools.count(1001)


def nueva_factura(proveedor):
    """Devuelve un diccionario con una factura válida."""
    subtotal = round(random.uniform(500, 25000), 2)
    iva = round(subtotal * 0.16, 2)
    total = round(subtotal + iva, 2)
    fecha = date(2026, 1, 1) + timedelta(days=random.randint(0, 300))
    return {
        "proveedor": proveedor[0],
        "rfc": proveedor[1],
        "numero": f"F-{next(contador_facturas):05d}",
        "fecha": fecha.strftime("%d/%m/%Y"),
        "concepto": random.choice(CONCEPTOS),
        "subtotal": subtotal,
        "iva": iva,
        "total": total,
    }


def fmt_monto(valor):
    return "" if valor is None else f"${valor:,.2f}"


def dibujar_pdf(ruta, d):
    """Dibuja la factura con texto digital (extraíble con Read PDF Text)."""
    c = canvas.Canvas(str(ruta), pagesize=letter)
    _, alto = letter

    c.setFont("Helvetica-Bold", 20)
    c.drawString(50, alto - 60, "FACTURA")

    lineas = [
        f"Proveedor: {d['proveedor']}",
        f"RFC: {d['rfc']}",
        f"Factura No: {d['numero']}",
        f"Fecha: {d['fecha']}",
        f"Concepto: {d['concepto']}",
        "",
        f"Subtotal: {fmt_monto(d['subtotal'])}",
        f"IVA (16%): {fmt_monto(d['iva'])}",
        f"Total: {fmt_monto(d['total'])}",
    ]
    c.setFont("Helvetica", 12)
    y = alto - 110
    for linea in lineas:
        c.drawString(50, y, linea)
        y -= 24

    c.setFont("Helvetica-Oblique", 9)
    c.drawString(50, 50, "Documento ficticio generado con fines de prueba.")
    c.save()


def construir_casos():
    """Lista de (datos, resultado_esperado, motivo)."""
    casos = []

    # 28 facturas válidas, repartidas entre los proveedores activos
    for i in range(28):
        casos.append((nueva_factura(PROVEEDORES[i % 4]), "VALIDA", ""))

    # 3 duplicados: mismo proveedor + mismo número que una válida
    for original, _, _ in random.sample(casos[:28], 3):
        casos.append(
            (
                dict(original),
                "DUPLICADA",
                f"Mismo proveedor y número ({original['numero']}) que otra factura",
            )
        )

    # 2 sin número de factura
    for i in range(2):
        d = nueva_factura(PROVEEDORES[i])
        d["numero"] = ""
        casos.append((d, "RECHAZADA", "Falta número de factura"))

    # 2 sin fecha
    for i in range(2):
        d = nueva_factura(PROVEEDORES[i + 1])
        d["fecha"] = ""
        casos.append((d, "RECHAZADA", "Falta fecha"))

    # 3 con total que no cuadra con subtotal + IVA
    for i in range(3):
        d = nueva_factura(PROVEEDORES[i])
        d["total"] = round(d["total"] + random.choice([50, 120, 300]), 2)
        casos.append((d, "RECHAZADA", "Subtotal + IVA no coincide con el total"))

    # 2 con fecha inválida
    for fecha_mala, prov in zip(["31/02/2026", "45/13/2026"], PROVEEDORES[:2]):
        d = nueva_factura(prov)
        d["fecha"] = fecha_mala
        casos.append((d, "RECHAZADA", f"Fecha inválida ({fecha_mala})"))

    # 2 de proveedor inactivo
    for _ in range(2):
        casos.append(
            (nueva_factura(PROVEEDOR_INACTIVO), "RECHAZADA", "Proveedor inactivo")
        )

    # 2 de proveedor inexistente
    for _ in range(2):
        casos.append(
            (
                nueva_factura(PROVEEDOR_DESCONOCIDO),
                "RECHAZADA",
                "Proveedor no existe en el catálogo",
            )
        )

    return casos


def ordenar_casos(casos):
    """Mezcla los casos y garantiza que cada duplicado quede DESPUÉS de su original
    (el robot procesa los archivos en orden alfabético)."""
    originales = [c for c in casos if c[1] != "DUPLICADA"]
    duplicados = [c for c in casos if c[1] == "DUPLICADA"]
    random.shuffle(originales)

    for dup in duplicados:
        pos_original = next(
            i
            for i, c in enumerate(originales)
            if c[1] == "VALIDA"
            and c[0]["numero"] == dup[0]["numero"]
            and c[0]["rfc"] == dup[0]["rfc"]
        )
        pos = random.randint(pos_original + 1, len(originales))
        originales.insert(pos, dup)

    return originales


def main():
    random.seed(SEED)
    CARPETA_SALIDA.mkdir(exist_ok=True)

    casos = ordenar_casos(construir_casos())

    with open(MANIFIESTO, "w", newline="", encoding="utf-8-sig") as f:
        escritor = csv.writer(f)
        escritor.writerow(
            [
                "archivo", "proveedor", "rfc", "numero_factura", "fecha",
                "subtotal", "iva", "total", "resultado_esperado", "motivo",
            ]
        )
        for idx, (d, resultado, motivo) in enumerate(casos, start=1):
            nombre = f"factura_{idx:03d}.pdf"
            dibujar_pdf(CARPETA_SALIDA / nombre, d)
            escritor.writerow(
                [
                    nombre, d["proveedor"], d["rfc"], d["numero"], d["fecha"],
                    d["subtotal"], d["iva"], d["total"], resultado, motivo,
                ]
            )

    resumen = {}
    for _, resultado, _ in casos:
        resumen[resultado] = resumen.get(resultado, 0) + 1

    print(f"Se generaron {len(casos)} PDFs en '{CARPETA_SALIDA}/'")
    for resultado, cantidad in resumen.items():
        print(f"  {resultado}: {cantidad}")
    print(f"Manifiesto con resultados esperados: {MANIFIESTO}")


if __name__ == "__main__":
    main()
