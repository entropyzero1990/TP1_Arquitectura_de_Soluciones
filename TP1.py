import asyncio
import sys 
import random
import re
import os
import pandas as pd
import matplotlib.pyplot as plt
from playwright.async_api import async_playwright
from textblob import TextBlob

# CONFIGURACIÓN INICIAL PARA WINDOWS
if sys.platform == 'win32':
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

# =================================
#  EXTRACCIÓN DE DATOS (SCRAPING)
# =================================
async def ejecutar_extraccion(url):
    try:
        async with async_playwright() as p:
            # Rutas de Brave (Asegurate que sean las correctas en tu PC)
            user_data_dir = r"C:\Users\resqu\AppData\Local\BraveSoftware\Brave-Browser\User Data"
            brave_path = r"C:\Program Files\BraveSoftware\Brave-Browser\Application\brave.exe"

            print("Iniciando Extracción (Cierra Brave antes)")
            context = await p.chromium.launch_persistent_context(
                user_data_dir,
                executable_path=brave_path,
                headless=False,
                args=["--profile-directory=Default"]
            )
            
            page = await context.new_page()
            await page.goto(url, wait_until="domcontentloaded", timeout=60000)
            await page.wait_for_selector('div[lang]', timeout=30000)

            # Script de inyección para capturar comentarios dinámicamente
            await page.evaluate("""
                window.bolsa = new Set();
                const observer = new MutationObserver(() => {
                    document.querySelectorAll('div[lang]').forEach(n => {
                        let txt = n.innerText.trim();
                        if(txt.length > 20 && !txt.includes("To view keyboard")) {
                            window.bolsa.add(txt);
                        }
                    });
                });
                observer.observe(document.body, {childList: true, subtree: true});
            """)

            for i in range(30): 
                await page.mouse.wheel(0, 800)
                await asyncio.sleep(random.uniform(2, 4)) 
                total = await page.evaluate("window.bolsa.size")
                print(f"Paso {i+1}/30 | Comentarios capturados: {total}")
                
                if i % 7 == 0:
                    await page.mouse.wheel(0, -150)

            datos_finales = await page.evaluate("Array.from(window.bolsa)")
            await context.close()
            return datos_finales
    except Exception as e:
        print(f"❌ Error en Scraping: {str(e)}")
        return []

# ===============================
#  LIMPIEZA Y ANÁLISIS POR REGLAS
# ===============================
def limpiar_texto(texto):
    if not isinstance(texto, str): return ""
    texto = texto.lower()
    # Limpiamos URLs y menciones, pero dejamos el texto base
    texto = re.sub(r'http\S+|www\S+|https\S+', '', texto, flags=re.MULTILINE)
    texto = re.sub(r'@\w+', '', texto) 
    return texto.strip()

def analizar_sentimiento_argentino(texto):
    if not texto: return 'Neutro'
    
    texto_min = texto.lower()

    #DICCIONARIO DE REFUERZO LOCAL
    # Agregamos términos de peso negativo en el contexto de X Argentina
    negativos_locales = [
        'turro', 'villero', 'retrasada', 'retrasado', 'nefasto', 'hdp', 
        'pelotudo', 'mierda', 'imposible', 'decime que sos', 'chorro', 
        'garca', 'pobre de mierda', 'fantasma', 'ridiculo', 'fracasado',
        'insoportable', 'asco', 'boludo', 'conchudo', 'forro'
    ]
    
    # Agregamos términos de peso positivo
    positivos_locales = [
        'genio', 'crack', 'basado', 'buenisimo', 'excelente', 'capo',
        'te amo', 'amo', 'joya', 'facha', 'grande', 'idolo'
    ]

    # Prioridad 1: Buscar negativos manuales
    if any(p in texto_min for p in negativos_locales):
        return 'Negativo'
    
    # Prioridad 2: Buscar positivos manuales
    if any(p in texto_min for p in positivos_locales):
        return 'Positivo'

    # Prioridad 3: Si no hay palabras clave, usamos TextBlob directo en español
    # Bajamos el umbral a 0 para que cualquier carga emocional cuente
    analisis = TextBlob(texto)
    polaridad = analisis.sentiment.polarity
    
    if polaridad > 0: return 'Positivo'
    elif polaridad < 0: return 'Negativo'
    else: return 'Neutro'

# ===============================
#  FUNCIÓN PRINCIPAL
# ===============================
async def main():
    url_objetivo = "https://x.com/porqueTTarg/status/2044771536020635848"
    
    comentarios = await ejecutar_extraccion(url_objetivo)
    
    if not comentarios:
        print("⚠️ No se capturaron datos.")
        return

    df = pd.DataFrame(comentarios, columns=["comentario"])
    df = df.drop_duplicates()
    
    print(f"--- Procesando {len(df)} registros únicos ---")
    df['comentario_limpio'] = df['comentario'].apply(limpiar_texto)
    df = df[df['comentario_limpio'].str.len() > 20]
    
    print("--- Analizando sentimientos (Diccionario Argentino) ---")
    df['Sentimiento'] = df['comentario_limpio'].apply(analizar_sentimiento_argentino)
    
    # Guardar resultados
    df.to_csv("resultado_final_analisis.csv", index=False, encoding='utf-8-sig')

    # --- GRÁFICO ---
    plt.figure(figsize=(10, 7))
    conteo = df['Sentimiento'].value_counts()
    
    colores_dict = {'Positivo': '#99ff99', 'Neutro': '#66b3ff', 'Negativo': '#ff9999'}
    colores_lista = [colores_dict.get(x, '#d3d3d3') for x in conteo.index]
    
    conteo.plot(kind='pie', 
                autopct='%1.1f%%', 
                colors=colores_lista, 
                startangle=140, 
                explode=[0.05]*len(conteo))

    plt.title('Sentimientos en X (Diccionario Local Argentino)')
    plt.ylabel('')
    plt.savefig('grafico_sentimientos.png')
    
    print("\nPROCESO COMPLETADO")
    print(conteo)
    plt.show()

if __name__ == "__main__":
    asyncio.run(main())