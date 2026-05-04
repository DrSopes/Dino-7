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
    pixels = img.load()
    width, height = img.size
    
    # Crear llibreria i cèl·lula GDS
    lib = gdspy.GdsLibrary()
    cell = lib.new_cell('LOGO_MACRO')
    
    # Mida del píxel en micròmetres (µm). 0.5 µm és prou petit.
    # Si la teva imatge fa 40x40 píxels, el logo farà 20x20 µm.
    PIXEL_SIZE = 0.5
    
    # Posició del logo respecte a la cantonada inferior esquerra del teu disseny
    OFFSET_X = 10.0 # µm
    OFFSET_Y = 10.0 # µm
    
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
    print(f"Generat {output_gds} amb èxit! Mida: {width}x{height} píxels.")

if __name__ == "__main__":
    create_logo_gds("src/logo.png", "src/logo_macro.gds")
