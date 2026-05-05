import gdspy
from PIL import Image, ImageOps
import os

def create_logo_gds(image_path, output_gds):
    if not os.path.exists(image_path):
        print(f"Error: No s'ha trobat la imatge {image_path}")
        return

    # GF180MCU: Capa Metal 5 (81, datatype 0)
    LAYER = 81
    DATATYPE = 0
    
    # Carregar imatge en escala de grisos
    img = Image.open(image_path).convert('L')
    
    # Treure l'espai en blanc inútil dels voltants perquè agafi només el dibuix
    img = ImageOps.invert(img)
    bbox = img.getbbox()
    if bbox:
        img = img.crop(bbox)
    img = ImageOps.invert(img)
    
    # REDUCCIÓ DE MIDA: La pujem de 60 a 200 per tenir moltíssima més resolució.
    # El disseny serà molt més gran i nítid
    original_width, original_height = img.size
    target_width = 200
    target_height = int((target_width / original_width) * original_height)
    
    img = img.resize((target_width, target_height), Image.Resampling.LANCZOS)
    
    # Opcional: Aumentar el contrast (binalitzar de manera agressiva)
    img = img.point(lambda p: 255 if p > 128 else 0)
    
    pixels = img.load()
    width, height = img.size
    
    lib = gdspy.GdsLibrary()
    cell = lib.new_cell('LOGO_MACRO')
    
    # Mida del rectangle base (el fem una mica més petit perquè tot càpiga en l'espai TT)
    # Si d'amplada fem 200 px * 0.4 µm = 80 µm d'amplada total (cap perfectament al xip!)
    PIXEL_SIZE = 0.4
    OFFSET_X = 10.0 # Separat dels marges
    OFFSET_Y = 10.0
    
    for y in range(height):
        for x in range(width):
            # El blanc és 255, el negre és 0
            if pixels[x, y] < 128:
                rect = gdspy.Rectangle(
                    (OFFSET_X + (x * PIXEL_SIZE), OFFSET_Y + ((height - y) * PIXEL_SIZE)),
                    (OFFSET_X + ((x + 1) * PIXEL_SIZE), OFFSET_Y + ((height - y + 1) * PIXEL_SIZE)),
                    layer=LAYER, datatype=DATATYPE
                )
                cell.add(rect)
                
    lib.write_gds(output_gds)
    print(f"Generat {output_gds} amb èxit! Resolució augmentada a: {width}x{height} píxels.")

if __name__ == "__main__":
    create_logo_gds("src/logo.png", "src/logo_macro.gds")
