import requests
from bs4 import BeautifulSoup
import json
import time
import random
import base64
import re
import os

# Configurações iniciais
BASE_URL = "https://vimm.net"
START_URL = "https://vimm.net/vault/Xbox360"
OUTPUT_FILE = "vimm_xbox360_games.json"
COVERS_DIR = "capas_xbox360" # Pasta onde as imagens serão salvas localmente

# Cabeçalhos para simular um navegador real e evitar bloqueios do servidor
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7",
}

def get_soup(url):
    """Faz a requisição e retorna o objeto BeautifulSoup."""
    try:
        response = requests.get(url, headers=HEADERS, timeout=15)
        response.raise_for_status()
        return BeautifulSoup(response.text, 'html.parser')
    except Exception as e:
        print(f"[ERRO] Falha ao acessar {url}: {e}")
        return None

def sanitize_filename(name):
    """Remove caracteres que o Windows/Linux não aceitam em nomes de arquivos."""
    return re.sub(r'[\\/*?:"<>|]', "", name)

def main():
    print("Iniciando o Web Scraping do Vimm's Lair...")
    
    # Cria a pasta de capas se não existir
    if not os.path.exists(COVERS_DIR):
        os.makedirs(COVERS_DIR)
        print(f"Pasta '{COVERS_DIR}' criada para salvar as imagens.")
    
    # Letras do alfabeto + 'number' (para a seção #)
    sections = ['number'] + [chr(i) for i in range(ord('A'), ord('Z')+1)]
    
    all_games = []

    # 1. Navegar pelas abas (A, B, C...)
    for section in sections:
        print(f"\n--- Processando seção: {section} ---")
        section_url = f"{BASE_URL}/vault/?p=list&system=Xbox360&section={section}"
        
        soup = get_soup(section_url)
        if not soup:
            continue

        # Encontrar a tabela de jogos
        game_links = []
        for a_tag in soup.select('table a[href^="/vault/"]'):
            href = a_tag.get('href')
            text = a_tag.get_text(strip=True)
            
            if href and text and '?p=' not in href and href != '/vault/999999':
                game_id_str = href.split('/')[-1]
                if game_id_str.isdigit():
                    full_link = f"{BASE_URL}{href}"
                    if full_link not in game_links:
                        game_links.append(full_link)

        print(f"Encontrados {len(game_links)} jogos na seção {section}.")

        # 2. Entrar em cada jogo e extrair os detalhes
        for game_url in game_links:
            # Espera um tempo aleatório para não sobrecarregar o servidor
            time.sleep(random.uniform(1.0, 3.0)) 
            
            game_soup = get_soup(game_url)
            if not game_soup:
                continue

            try:
                # ID
                game_id_elem = game_soup.select_one('#dl_form > input[type=hidden]:nth-child(1)')
                if game_id_elem and game_id_elem.has_attr('value'):
                    game_id = game_id_elem['value']
                else:
                    game_id = game_url.split('/')[-1] 

                # NOME 
                name_elem = game_soup.select_one('#canvas')
                game_name = "Desconhecido"
                if name_elem and name_elem.has_attr('data-v'):
                    try:
                        encoded_name = name_elem['data-v']
                        game_name = base64.b64decode(encoded_name).decode('utf-8')
                    except:
                        pass

                # IMAGEM (DOWNLOAD LOCAL + LINK DO GITHUB NO JSON)
                img_elem = game_soup.select_one('#screenShot')
                img_url = ""
                if img_elem and img_elem.has_attr('style'):
                    style_text = img_elem['style']
                    match = re.search(r"url\(['\"]?(.*?)['\"]?\)", style_text)
                    if match:
                        extracted_url = match.group(1)
                        if extracted_url.startswith('//'):
                            original_img_url = f"https:{extracted_url}"
                        elif extracted_url.startswith('/'):
                            original_img_url = f"{BASE_URL}{extracted_url}"
                        else:
                            original_img_url = extracted_url
                            
                        # Lógica para baixar a imagem enganando a proteção do Vimm
                        safe_name = sanitize_filename(game_name)
                        
                        # Substitui espaços por %20 para gerar um link web válido
                        safe_name_url = safe_name.replace(" ", "%20")
                        
                        img_path = os.path.join(COVERS_DIR, f"{safe_name}.jpg")
                        github_img_url = f"https://github.com/telesiago/XBOX-360-Cover/blob/main/capas_xbox360/{safe_name_url}.jpg?raw=true"
                        
                        # Se a imagem ainda não foi baixada, nós a baixamos
                        if not os.path.exists(img_path):
                            img_headers = HEADERS.copy()
                            img_headers["Referer"] = game_url # <- Isso engana o site e permite pegar a capa!
                            
                            try:
                                img_res = requests.get(original_img_url, headers=img_headers, stream=True)
                                if img_res.status_code == 200:
                                    with open(img_path, 'wb') as f:
                                        for chunk in img_res.iter_content(1024):
                                            f.write(chunk)
                                    img_url = github_img_url # Atualiza o JSON com o link do GitHub codificado
                                else:
                                    img_url = original_img_url # Fallback caso falhe
                            except Exception as e:
                                print(f"  -> Falha ao baixar capa de {game_name}: {e}")
                                img_url = original_img_url
                        else:
                            img_url = github_img_url # Se já existe, aponta para o GitHub com %20

                # TAMANHO
                size_elem = game_soup.select_one('#dl_size')
                game_size = size_elem.get_text(strip=True) if size_elem else "0 GB"

                # DATA
                date_elem = game_soup.select_one('#data-date')
                game_date = date_elem.get_text(strip=True) if date_elem else "Data Desconhecida"

                # LINK DE DOWNLOAD
                download_link = game_url

                # Cria o dicionário do jogo
                game_data = {
                    "id": game_id,
                    "name": game_name,
                    "img": img_url,
                    "size": game_size,
                    "date": game_date,
                    "link": download_link
                }

                all_games.append(game_data)
                
                print("\n" + "-"*50)
                print(f"✅ Jogo Extraído com Sucesso:")
                print(json.dumps(game_data, ensure_ascii=False, indent=4))
                print("-"*50)

            except Exception as e:
                print(f"\n[ERRO] Falha ao processar dados de {game_url}: {e}")

    # 3. Salvar tudo no arquivo JSON
    print("\nSalvando os dados extraídos no arquivo JSON...")
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        json.dump(all_games, f, ensure_ascii=False, indent=4)
        
    print(f"\nFinalizado! {len(all_games)} jogos foram salvos em '{OUTPUT_FILE}'.")
    print(f"As capas foram baixadas na pasta '{COVERS_DIR}'.")

if __name__ == "__main__":
    main()