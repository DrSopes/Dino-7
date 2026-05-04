import gdspy
from PIL import Image
import os

def create_logo_gds(image_path, output_gds):
    if not os.path.exists(image_path):
        print(f"Error: No s'ha trobat la imatge {image_path}")
        return

    # GF180MCU: La capa Metal 5 és la 81, tipus 0.
    # Utilitzem Met5 perquè està per sobre de les cèl·lules estàndard i no sol interferir.
    LAYER = 81
    DATATYPE = 0
    
    # Carregar la imatge i convertir-la a escala de grisos
    img = Image.open(image_path).convert('L')
    
    # REDUCCIÓ DE MIDA (Nou!): 
    # El teu logo era massa gran (1774 px). El reduïm a un màxim de 60 píxels d'amplada 
    # per assegurar-nos que cap correctament i que no saturen l'enrutador.
    original_width, original_height = img.size
    target_width = 60
    target_height = int((target_width / original_width) * original_height)
    
    # Redimensionem amb filtre de qualitat alta (LANCZOS substitueix l'antic ANTIALIAS)
    img = img.resize((target_width, target_height), Image.Resampling.LANCZOS)
    
    pixels = img.load()
    width, height = img.size
    
    # Crear llibreria i cèl·lula GDS
    lib = gdspy.GdsLibrary()
    cell = lib.new_cell('LOGO_MACRO')
    
    # Mida del píxel en micròmetres (µm). 0.5 µm és prou petit i segur.
    PIXEL_SIZE = 0.5
    
    # Posició del logo respecte a la cantonada inferior esquerra de la MACRO
    OFFSET_X = 0.0 # µm
    OFFSET_Y = 0.0 # µm
    
    for y in range(height):
        for x in range(width):
            # Si el píxel és fosc (menys de 128), dibuixem metall
            if pixels[x, y] < 128:
                # La coordenada Y a les imatges va de dalt a baix, a GDS de baix a dalt
                rect = gdspy.Rectangle(
                    (OFFSET_X + (x * PIXEL_SIZE), OFFSET_Y + ((height - y) * PIXEL_SIZE)),
                    (OFFSET_X + ((x + 1) * PIXEL_SIZE), OFFSET_Y + ((height - y + 1) * PIXEL_SIZE)),
                    layer=LAYER, datatype=DATATYPE
                )
                cell.add(rect)
                
    lib.write_gds(output_gds)
    print(f"Generat {output_gds} amb èxit! Mida redimensionada: {width}x{height} píxels.")

if __name__ == "__main__":
    # Com que executem des de l'arrel del repo via GitHub Actions, les rutes han de ser així:
    create_logo_gds("src/logo.png", "src/logo_macro.gds")
