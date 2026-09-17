#!/usr/bin/env python3
"""
desktop_utils.py
================
Utilitários de suporte para a versão Desktop do Gerador Automático de Tutoriais em Vídeo.
Inclui:
- Exportação e importação de projetos (JSON e pacotes ZIP com mídias completas)
- Geração instantânea de frame preview composto com PIL e MoviePy
- Gerenciamento de arquivos temporários e sanitização de caminhos multiplataforma
"""

import asyncio
import io
import json
import math
import os
import re
import shutil
import textwrap
import time
import unicodedata
import zipfile
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from PIL import Image, ImageDraw
from moviepy import VideoFileClip

from gerador_generico import carregar_fonte, sintetizar_audio

# ==============================================================================
# Constantes Globais
# ==============================================================================

OPCOES_VOZES = {
    "pt-BR-AntonioNeural (Masculino - Natural)": "pt-BR-AntonioNeural",
    "pt-BR-FranciscaNeural (Feminino - Suave)": "pt-BR-FranciscaNeural",
    "pt-BR-ThalitaMultilingualNeural (Feminino - Expressivo)": "pt-BR-ThalitaMultilingualNeural",
    "pt-PT-RaquelNeural (Português de Portugal - Feminino)": "pt-PT-RaquelNeural",
    "pt-PT-DuarteNeural (Português de Portugal - Masculino)": "pt-PT-DuarteNeural",
    "Outra voz personalizada": "custom",
}

OPCOES_RESOLUCAO = {
    "Full HD 1080p (1920x1080)": (1920, 1080),
    "HD 720p (1280x720)": (1280, 720),
    "Vertical Shorts/Reels (1080x1920)": (1080, 1920),
}

TAXAS_FALA = ["-20%", "-10%", "+0%", "+10%", "+20%", "+30%"]


# ==============================================================================
# Sanitização e Tratamento de Nomes de Arquivo
# ==============================================================================

def sanitizar_nome_arquivo(nome: str) -> str:
    """Gera um nome de arquivo seguro a partir do título."""
    nfkd = unicodedata.normalize("NFKD", nome)
    nome_sem_acento = "".join([c for c in nfkd if not unicodedata.combining(c)])
    nome_limpo = re.sub(r"[^\w\s-]", "", nome_sem_acento).strip().lower()
    nome_limpo = re.sub(r"[-\s]+", "_", nome_limpo)
    return nome_limpo or "tutorial_final"


# ==============================================================================
# Geração de Frame Preview (Snapshot de Alta Resolução)
# ==============================================================================

def gerar_previa_frame_composto(
    caminho_midia: str,
    texto_tarja: str,
    texto_legenda: str,
    exibir_tarja: bool,
    exibir_legenda: bool,
    resolucao: Tuple[int, int] = (1920, 1080),
) -> Image.Image:
    """Gera um frame único em alta resolução com a mídia de fundo e as camadas visuais sobrepostas."""
    vid_w, vid_h = resolucao
    caminho = Path(caminho_midia)
    ext = caminho.suffix.lower()

    if ext in [".png", ".jpg", ".jpeg", ".webp", ".bmp"]:
        img_orig = Image.open(caminho).convert("RGBA")
        img_orig.thumbnail((vid_w, vid_h), Image.Resampling.LANCZOS)
        base = Image.new("RGBA", (vid_w, vid_h), (15, 23, 42, 255))
        pos_x = (vid_w - img_orig.width) // 2
        pos_y = (vid_h - img_orig.height) // 2
        base.paste(img_orig, (pos_x, pos_y), img_orig)
    else:
        clip = VideoFileClip(str(caminho))
        t = min(1.0, max(0.0, clip.duration / 2)) if clip.duration else 0.0
        frame_arr = clip.get_frame(t)
        clip.close()
        base = Image.fromarray(frame_arr).convert("RGBA")
        if base.size != (vid_w, vid_h):
            base = base.resize((vid_w, vid_h), Image.Resampling.LANCZOS)

    tem_tarja_inferior = False
    if exibir_tarja and texto_tarja.strip():
        tem_tarja_inferior = True
        fonte_tarja = carregar_fonte(30, bold=True)
        txt = texto_tarja.strip()
        linhas_orig = txt.splitlines()
        linhas = []
        for l in linhas_orig:
            linhas.extend(textwrap.wrap(l, width=55) if len(l) > 55 else [l])
        txt_fmt = "\n".join(linhas) if linhas else txt

        pad_x, pad_y = 26, 14
        temp = Image.new("RGBA", (10, 10))
        d_temp = ImageDraw.Draw(temp)
        bb = d_temp.multiline_textbbox((0, 0), txt_fmt, font=fonte_tarja, spacing=6)
        tw = int(math.ceil(bb[2] - bb[0]))
        th = int(math.ceil(bb[3] - bb[1]))
        lw = int(tw + pad_x * 2 + 14)
        lh = int(th + pad_y * 2)
        tarja_img = Image.new("RGBA", (lw, lh), (0, 0, 0, 0))
        d_tarja = ImageDraw.Draw(tarja_img)
        d_tarja.rounded_rectangle(
            [(0, 0), (lw - 1, lh - 1)],
            radius=12,
            fill=(15, 23, 42, 225),
            outline=(51, 65, 85, 220),
            width=2,
        )
        d_tarja.rounded_rectangle([(4, 4), (10, lh - 5)], radius=3, fill=(59, 130, 246, 255))
        d_tarja.multiline_text(
            (pad_x + 8, pad_y - int(bb[1]) + (lh - 2 * pad_y - th) // 2),
            txt_fmt,
            font=fonte_tarja,
            fill=(255, 255, 255, 255),
            spacing=6,
        )
        base.paste(tarja_img, (50, vid_h - lh - 50), tarja_img)

    if exibir_legenda and texto_legenda.strip():
        fonte_leg = carregar_fonte(24, bold=True)
        max_txt_w = int(vid_w * 0.72)
        chars = max(35, int(max_txt_w / (24 * 0.58)))
        linhas = []
        for p in texto_legenda.strip().splitlines():
            if p.strip():
                linhas.extend(textwrap.wrap(p.strip(), width=chars))
        txt_fmt = "\n".join(linhas) if linhas else texto_legenda.strip()
        pad_x, pad_y = 22, 10
        temp = Image.new("RGBA", (10, 10))
        d_temp = ImageDraw.Draw(temp)
        bb = d_temp.multiline_textbbox((0, 0), txt_fmt, font=fonte_leg, spacing=6, align="center")
        tw = int(math.ceil(bb[2] - bb[0]))
        th = int(math.ceil(bb[3] - bb[1]))
        lw = int(tw + pad_x * 2)
        lh = int(th + pad_y * 2)
        leg_img = Image.new("RGBA", (lw, lh), (0, 0, 0, 0))
        d_leg = ImageDraw.Draw(leg_img)
        d_leg.rounded_rectangle(
            [(0, 0), (lw - 1, lh - 1)],
            radius=10,
            fill=(10, 15, 25, 215),
            outline=(255, 255, 255, 50),
            width=1,
        )
        d_leg.multiline_text(
            (pad_x - int(bb[0]), pad_y - int(bb[1])),
            txt_fmt,
            font=fonte_leg,
            fill=(255, 255, 255, 245),
            spacing=6,
            align="center",
        )
        desloc = 130 if tem_tarja_inferior else 35
        base.paste(leg_img, ((vid_w - lw) // 2, vid_h - lh - desloc), leg_img)

    return base.convert("RGB")


# ==============================================================================
# Prévia Rápida de Áudio TTS
# ==============================================================================

def sintetizar_audio_sincrono(texto: str, caminho_saida: Path, voz: str, taxa: str = "+0%") -> bool:
    """Gera áudio MP3 síncrono para prévia antes da renderização."""
    try:
        caminho_saida.parent.mkdir(parents=True, exist_ok=True)
        asyncio.run(
            sintetizar_audio(
                texto=texto,
                caminho_saida=caminho_saida,
                voz=voz,
                taxa=taxa,
                volume="+0%",
            )
        )
        return caminho_saida.is_file()
    except Exception as e:
        print(f"Erro ao sintetizar áudio de prévia: {e}")
        return False


# ==============================================================================
# Serialização e Deserialização de Projetos (JSON / ZIP)
# ==============================================================================

def construir_dict_projeto(titulo: str, config_geral: Dict[str, Any], cenas: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Monta a estrutura padronizada de dicionário do projeto."""
    cenas_serializadas = []
    for idx, c in enumerate(cenas, 1):
        c_id = c.get("id") or f"passo_{idx:02d}"
        c_titulo = c.get("titulo") or f"Cena {idx}"
        midia_path = c.get("caminho_midia", "")

        narracao = c.get("texto_narracao", "")
        legenda = c.get("legenda", "")

        cena_dict = {
            "id": c_id,
            "titulo": c_titulo,
            "video_path": midia_path,
            "texto_narracao": narracao,
            "voz": c.get("voz") or config_geral.get("voz_padrao", "pt-BR-AntonioNeural"),
            "taxa_fala": c.get("taxa_fala") or config_geral.get("taxa_fala_padrao", "+0%"),
            "pausa_final": float(c.get("pausa_final", config_geral.get("pausa_final_padrao", 0.5))),
            "legenda": legenda,
            "tarja_visual": c.get("tarja_visual", ""),
            "exibir_legenda": bool(c.get("exibir_legenda", True)),
            "exibir_overlay": bool(c.get("exibir_overlay", True)),
        }

        if c.get("exibir_overlay") and c.get("tarja_visual"):
            cena_dict["overlay_texto"] = {
                "texto": c["tarja_visual"],
                "posicao": "inferior_esquerdo",
            }
        else:
            cena_dict["overlay_texto"] = None

        cenas_serializadas.append(cena_dict)

    return {
        "titulo_tutorial": titulo,
        "configuracoes_gerais": {
            "voz_padrao": config_geral.get("voz_padrao", "pt-BR-AntonioNeural"),
            "taxa_fala_padrao": config_geral.get("taxa_fala_padrao", "+0%"),
            "volume_padrao": config_geral.get("volume_padrao", "+0%"),
            "resolucao_padrao": list(config_geral.get("resolucao_padrao", [1920, 1080])),
            "fps_padrao": int(config_geral.get("fps_padrao", 30)),
            "pausa_final_padrao": float(config_geral.get("pausa_final_padrao", 0.5)),
            "video_saida": f"saida/{sanitizar_nome_arquivo(titulo)}.mp4",
            "manter_audios_temp": bool(config_geral.get("manter_audios_temp", False)),
        },
        "cenas": cenas_serializadas,
    }


def salvar_projeto_json(caminho_arquivo: Path, titulo: str, config_geral: Dict[str, Any], cenas: List[Dict[str, Any]]) -> None:
    """Salva a configuração do projeto em um arquivo JSON."""
    caminho_arquivo.parent.mkdir(parents=True, exist_ok=True)
    dados = construir_dict_projeto(titulo, config_geral, cenas)
    with open(caminho_arquivo, "w", encoding="utf-8") as f:
        json.dump(dados, f, indent=2, ensure_ascii=False)


def exportar_projeto_zip(
    caminho_zip: Path,
    titulo: str,
    config_geral: Dict[str, Any],
    cenas: List[Dict[str, Any]],
) -> None:
    """Cria um arquivo ZIP autocontido com o JSON do projeto e todos os arquivos de mídia."""
    caminho_zip.parent.mkdir(parents=True, exist_ok=True)
    dados = construir_dict_projeto(titulo, config_geral, cenas)

    with zipfile.ZipFile(caminho_zip, "w", zipfile.ZIP_DEFLATED) as zf:
        for idx, c in enumerate(dados["cenas"], 1):
            caminho_local = c.get("video_path")
            if caminho_local and Path(caminho_local).is_file():
                arq = Path(caminho_local)
                ext = arq.suffix
                caminho_interno = f"cenas/{c['id']}{ext}"
                zf.write(str(arq), arcname=caminho_interno)
                c["video_path"] = caminho_interno

        conteudo_json = json.dumps(dados, indent=2, ensure_ascii=False)
        zf.writestr("config_projeto.json", conteudo_json.encode("utf-8"))


def carregar_projeto_json(caminho_arquivo: Path) -> Dict[str, Any]:
    """Carrega dados estruturados de um arquivo JSON existente."""
    if not caminho_arquivo.is_file():
        raise FileNotFoundError(f"Arquivo não encontrado: {caminho_arquivo}")
    with open(caminho_arquivo, "r", encoding="utf-8") as f:
        return json.load(f)


def descompactar_e_importar_zip(caminho_zip: Path, pasta_destino: Path) -> Dict[str, Any]:
    """Extrai um pacote ZIP e ajusta os caminhos das mídias para a pasta de destino."""
    if not caminho_zip.is_file():
        raise FileNotFoundError(f"Arquivo ZIP não encontrado: {caminho_zip}")

    pasta_destino.mkdir(parents=True, exist_ok=True)

    with zipfile.ZipFile(caminho_zip, "r") as zf:
        zf.extractall(pasta_destino)

    arquivos_json = list(pasta_destino.glob("*.json"))
    if not arquivos_json:
        raise ValueError("O arquivo ZIP não contém nenhum manifesto de projeto .json válido.")

    manifesto = arquivos_json[0]
    dados = carregar_projeto_json(manifesto)

    cenas = dados.get("cenas") or dados.get("passos", [])
    for c in cenas:
        vp = c.get("video_path")
        if vp:
            caminho_resolvido = pasta_destino / vp
            if caminho_resolvido.is_file():
                c["video_path"] = str(caminho_resolvido)

    return dados


def limpar_arquivos_temporarios(pasta_base: Path = Path("temp_desktop")) -> int:
    """Remove pastas e arquivos de jobs temporários anteriores."""
    removidos = 0
    if pasta_base.exists():
        try:
            shutil.rmtree(pasta_base)
            removidos += 1
        except Exception:
            pass
    return removidos


def gerar_miniatura_midia(
    caminho_midia: str,
    largura_max: int = 220,
    altura_max: int = 124,
) -> Optional[Tuple[Image.Image, str, str, str]]:
    """
    Gera miniatura proporcional e metadados descritivos de uma mídia (vídeo ou imagem).
    Retorna: (imagem_pil_miniatura, nome_arquivo, tipo_e_resolucao, detalhes_extras) ou None.
    """
    if not caminho_midia:
        return None
    p = Path(caminho_midia)
    if not p.is_file():
        return None

    ext = p.suffix.lower()
    tamanho_bytes = p.stat().st_size
    tamanho_str = f"{tamanho_bytes / (1024 * 1024):.1f} MB" if tamanho_bytes > 1024 * 1024 else f"{tamanho_bytes / 1024:.0f} KB"

    try:
        if ext in [".png", ".jpg", ".jpeg", ".webp", ".bmp"]:
            with Image.open(p) as img_orig:
                w_orig, h_orig = img_orig.size
                tipo_resolucao = f"🖼️ Imagem {ext.replace('.', '').upper()} ({w_orig}x{h_orig})"
                detalhes = f"Tamanho: {tamanho_str}"

                img_thumb = img_orig.convert("RGBA")
                img_thumb.thumbnail((largura_max, altura_max), Image.Resampling.LANCZOS)
                return img_thumb, p.name, tipo_resolucao, detalhes
        else:
            clip = VideoFileClip(str(p))
            dur = float(clip.duration or 0.0)
            w_orig, h_orig = clip.w, clip.h
            t_frame = min(1.0, max(0.0, dur / 2.0)) if dur else 0.0
            frame_arr = clip.get_frame(t_frame)
            clip.close()

            minutos = int(dur // 60)
            segundos = int(dur % 60)
            dur_str = f"{minutos}m {segundos:02d}s" if minutos > 0 else f"{dur:.1f}s"

            tipo_resolucao = f"🎥 Vídeo {ext.replace('.', '').upper()} ({w_orig}x{h_orig})"
            detalhes = f"Duração: {dur_str} • Tamanho: {tamanho_str}"

            img_base = Image.fromarray(frame_arr).convert("RGBA")
            img_base.thumbnail((largura_max, altura_max), Image.Resampling.LANCZOS)
            return img_base, p.name, tipo_resolucao, detalhes
    except Exception as e:
        print(f"Erro ao extrair miniatura de {caminho_midia}: {e}")
        return None

