#!/usr/bin/env python3
"""
gerador_generico.py
===================
Motor modular e genérico para automação de tutoriais em vídeo.

Arquitetura:
- 100% Data-Driven: Configuração completa via JSON (cenas/passos dinâmicos).
- Suporte a múltiplas vozes por cena ou global via edge-tts.
- Padronização automática de resolução (ex: 1080p) preservando proporção (evita falhas de concatenação).
- Sincronização inteligente com congelamento de quadro (Freeze Frame).
- Inserção de camadas visuais: overlay de texto estilizado (Lower-third) e imagem de destaque (logo/badge/screenshot).
- Validador robusto pré-voo para detecção de arquivos ausentes e modo de placeholders.
"""

import argparse
import asyncio
import json
import math
import os
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

import edge_tts
from moviepy import AudioFileClip, ColorClip, CompositeVideoClip, ImageClip, VideoFileClip, concatenate_videoclips, vfx
import numpy as np
from PIL import Image, ImageDraw, ImageFont


# ==============================================================================
# Modelos de Dados e Configurações
# ==============================================================================

@dataclass
class ConfiguracaoGeral:
    voz_padrao: str = "pt-BR-AntonioNeural"
    taxa_fala_padrao: str = "+0%"
    volume_padrao: str = "+0%"
    resolucao_padrao: Tuple[int, int] = (1920, 1080)
    fps_padrao: int = 30
    pausa_final_padrao: float = 0.5
    video_saida: Path = Path("saida/tutorial_final.mp4")
    manter_audios_temp: bool = False


@dataclass
class OverlayTextoConfig:
    texto: str
    posicao: Union[str, Tuple[int, int]] = "inferior_esquerdo"
    duracao: Optional[float] = None  # None = durante toda a cena


@dataclass
class ImagemDestaqueConfig:
    caminho: Path
    posicao: Union[str, Tuple[int, int]] = "superior_direito"
    tamanho_max: Tuple[int, int] = (320, 180)
    duracao: Optional[float] = None  # None = durante toda a cena


@dataclass
class Cena:
    id: str
    titulo: str
    video_path: Path
    texto_narracao: str
    voz: Optional[str] = None
    taxa_fala: Optional[str] = None
    overlay_texto: Optional[OverlayTextoConfig] = None
    imagem_destaque: Optional[ImagemDestaqueConfig] = None
    pausa_final: Optional[float] = None
    legenda: Optional[str] = None
    tarja_visual: Optional[str] = None
    exibir_legenda: bool = True


# ==============================================================================
# Módulo de Validação e Leitura de Configuração
# ==============================================================================

def carregar_configuracao(caminho_config: Path) -> Tuple[str, ConfiguracaoGeral, List[Cena]]:
    """Lê e converte o JSON em objetos estruturados."""
    if not caminho_config.is_file():
        raise FileNotFoundError(f"Arquivo de configuração não encontrado: {caminho_config}")

    with open(caminho_config, "r", encoding="utf-8") as f:
        dados = json.load(f)

    titulo_tutorial = dados.get("titulo_tutorial", dados.get("titulo", "Vídeo Tutorial"))
    cfg_raw = dados.get("configuracoes_gerais", dados.get("configuracoes", {}))

    resolucao_raw = cfg_raw.get("resolucao_padrao", [1920, 1080])
    resolucao = (int(resolucao_raw[0]), int(resolucao_raw[1]))

    saida_str = cfg_raw.get("video_saida", "saida/tutorial_final.mp4")

    config_geral = ConfiguracaoGeral(
        voz_padrao=cfg_raw.get("voz_padrao", cfg_raw.get("voz", "pt-BR-AntonioNeural")),
        taxa_fala_padrao=cfg_raw.get("taxa_fala_padrao", cfg_raw.get("taxa_fala", "+0%")),
        volume_padrao=cfg_raw.get("volume_padrao", cfg_raw.get("volume", "+0%")),
        resolucao_padrao=resolucao,
        fps_padrao=int(cfg_raw.get("fps_padrao", cfg_raw.get("fps", 30))),
        pausa_final_padrao=float(cfg_raw.get("pausa_final_padrao", cfg_raw.get("pausa_final_cena", 0.5))),
        video_saida=Path(saida_str),
        manter_audios_temp=bool(cfg_raw.get("manter_audios_temp", False)),
    )

    cenas_raw = dados.get("cenas") or dados.get("passos")
    if not isinstance(cenas_raw, list) or len(cenas_raw) == 0:
        raise ValueError("O arquivo de configuração deve conter uma lista não-vazia em 'cenas' ou 'passos'.")

    lista_cenas: List[Cena] = []
    for i, c_raw in enumerate(cenas_raw, 1):
        id_cena = c_raw.get("id", f"cena_{i:02d}")
        titulo_cena = c_raw.get("titulo", f"Cena {i}")

        video_path_str = (
            c_raw.get("video_path")
            or c_raw.get("video")
            or c_raw.get("imagem_path")
            or c_raw.get("imagem")
            or c_raw.get("captura_tela")
            or c_raw.get("midia_path")
        )
        if not video_path_str:
            raise ValueError(f"Cena {i} ({id_cena}) não possui a propriedade obrigatória 'video_path' ou 'imagem_path'.")
        video_path = Path(video_path_str)
        if not video_path.is_file() and (caminho_config.parent / video_path).is_file():
            video_path = caminho_config.parent / video_path

        narracao_str = (
            c_raw.get("texto_narracao")
            or c_raw.get("narracao")
            or c_raw.get("texto_fala")
            or c_raw.get("fala")
            or c_raw.get("legenda")
        )
        if not narracao_str:
            raise ValueError(f"Cena {i} ({id_cena}) não possui a propriedade obrigatória 'texto_narracao' ou 'legenda'.")

        voz = c_raw.get("voz")
        taxa = c_raw.get("taxa_fala")
        pausa = float(c_raw["pausa_final"]) if "pausa_final" in c_raw else None

        # Overlay de texto / Tarja visual
        overlay_cfg: Optional[OverlayTextoConfig] = None
        tarja_str = c_raw.get("tarja_visual") or c_raw.get("tarja")
        legenda_str = c_raw.get("legenda") or c_raw.get("texto_legenda")
        if "overlay_texto" in c_raw and c_raw["overlay_texto"]:
            val = c_raw["overlay_texto"]
            if isinstance(val, str):
                overlay_cfg = OverlayTextoConfig(texto=val)
            elif isinstance(val, dict):
                overlay_cfg = OverlayTextoConfig(
                    texto=val.get("texto", ""),
                    posicao=val.get("posicao", "inferior_esquerdo"),
                    duracao=val.get("duracao"),
                )
        elif tarja_str:
            overlay_cfg = OverlayTextoConfig(texto=str(tarja_str))
        elif legenda_str and ("exibir_tarja" not in c_raw or c_raw.get("exibir_tarja")):
            # Fallback de compatibilidade
            overlay_cfg = OverlayTextoConfig(texto=str(legenda_str))

        # Imagem de destaque
        imagem_cfg: Optional[ImagemDestaqueConfig] = None
        if "imagem_destaque" in c_raw and c_raw["imagem_destaque"]:
            val_img = c_raw["imagem_destaque"]
            if isinstance(val_img, str):
                imagem_cfg = ImagemDestaqueConfig(caminho=Path(val_img))
            elif isinstance(val_img, dict):
                caminho_img = Path(val_img.get("caminho", ""))
                tam_max = tuple(val_img.get("tamanho_max", [320, 180]))
                imagem_cfg = ImagemDestaqueConfig(
                    caminho=caminho_img,
                    posicao=val_img.get("posicao", "superior_direito"),
                    tamanho_max=tam_max,
                    duracao=val_img.get("duracao"),
                )

        lista_cenas.append(
            Cena(
                id=id_cena,
                titulo=titulo_cena,
                video_path=video_path,
                texto_narracao=narracao_str,
                voz=voz,
                taxa_fala=taxa,
                overlay_texto=overlay_cfg,
                imagem_destaque=imagem_cfg,
                pausa_final=pausa,
                legenda=str(legenda_str) if legenda_str else None,
                tarja_visual=str(tarja_str) if tarja_str else (overlay_cfg.texto if overlay_cfg else None),
                exibir_legenda=bool(c_raw.get("exibir_legenda", True)),
            )
        )

    return titulo_tutorial, config_geral, lista_cenas


def validar_arquivos(
    cenas: List[Cena],
    resolucao: Tuple[int, int],
    fps: int,
    gerar_placeholders: bool = False,
) -> None:
    """Verifica a integridade dos arquivos e gera placeholders se solicitado."""
    videos_faltando: List[Tuple[int, Cena]] = []
    imagens_faltando: List[Tuple[int, Cena, Path]] = []

    for i, cena in enumerate(cenas, 1):
        if not cena.video_path.is_file():
            videos_faltando.append((i, cena))

        if cena.imagem_destaque and not cena.imagem_destaque.caminho.is_file():
            imagens_faltando.append((i, cena, cena.imagem_destaque.caminho))

    if not videos_faltando and not imagens_faltando:
        return

    if gerar_placeholders:
        print(f"⚠️  Detectados arquivos ausentes. Modo '--gerar-placeholders' ativo. Criando mídias de demonstração...")

        # Criar vídeos ou imagens de tela ausentes
        for idx, cena in videos_faltando:
            ext = cena.video_path.suffix.lower()
            if ext in [".png", ".jpg", ".jpeg", ".webp", ".bmp"]:
                print(f"   ➕ [Imagem/Captura Placeholder] Cena {idx:02d}: '{cena.titulo}' -> {cena.video_path}")
                criar_imagem_placeholder(cena.video_path, texto=cena.titulo[:25])
            else:
                print(f"   ➕ [Vídeo Placeholder] Cena {idx:02d}: '{cena.titulo}' -> {cena.video_path}")
                criar_video_placeholder(
                    caminho_saida=cena.video_path,
                    numero_cena=idx,
                    total_cenas=len(cenas),
                    titulo=cena.titulo,
                    resolucao=resolucao,
                    fps=fps,
                )

        # Criar imagens de destaque ausentes
        for idx, cena, caminho_img in imagens_faltando:
            print(f"   ➕ [Imagem Placeholder] Cena {idx:02d}: Criando imagem provisória -> {caminho_img}")
            criar_imagem_placeholder(caminho_img, texto=cena.titulo[:20])

        print("   ✅ Todas as mídias de demonstração foram geradas com sucesso.\n")
        return

    # Se não ativou placeholders, exibe relatório de erro detalhado e encerra
    print("\n" + "=" * 70)
    print("❌ ERRO DE VALIDAÇÃO: Arquivos necessários não foram encontrados no disco:")
    print("=" * 70)

    if videos_faltando:
        print("\n📹 Vídeos de tela ausentes:")
        for idx, cena in videos_faltando:
            print(f"   • Passo {idx:02d} [{cena.id}]: {cena.video_path} (esperado)")

    if imagens_faltando:
        print("\n🖼️  Imagens de destaque ausentes:")
        for idx, cena, caminho_img in imagens_faltando:
            print(f"   • Passo {idx:02d} [{cena.id}]: {caminho_img} (esperado)")

    print("\n🛠️  COMO RESOLVER:")
    print("   1. Adicione os vídeos brutos (.mp4) e imagens (.png/.jpg) nos caminhos indicados acima.")
    print("   2. OU use a flag '--gerar-placeholders' para testar a renderização completa agora:")
    print("      $ python gerador_generico.py --gerar-placeholders\n")
    sys.exit(1)


# ==============================================================================
# Módulo de Criação de Placeholders
# ==============================================================================

def carregar_fonte(tamanho: int, bold: bool = False) -> ImageFont.ImageFont:
    """Carrega fonte TrueType do sistema de forma segura e compatível com Linux e Windows."""
    # Lista de caminhos comuns para fontes em Linux, Windows e macOS
    candidatas = [
        # Linux
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
        "/usr/share/fonts/truetype/freefont/FreeSansBold.ttf" if bold else "/usr/share/fonts/truetype/freefont/FreeSans.ttf",
        # Windows
        os.path.join(os.environ.get("WINDIR", "C:\\Windows"), "Fonts", "arialbd.ttf" if bold else "arial.ttf"),
        os.path.join(os.environ.get("WINDIR", "C:\\Windows"), "Fonts", "segoeuib.ttf" if bold else "segoeui.ttf"),
        os.path.join(os.environ.get("WINDIR", "C:\\Windows"), "Fonts", "calibrib.ttf" if bold else "calibri.ttf"),
        os.path.join(os.environ.get("WINDIR", "C:\\Windows"), "Fonts", "tahomabd.ttf" if bold else "tahoma.ttf"),
        # macOS
        "/System/Library/Fonts/HelveticaNeue.ttc",
        "/Library/Fonts/Arial.ttf",
    ]
    for c in candidatas:
        if c and os.path.exists(c):
            try:
                return ImageFont.truetype(c, tamanho)
            except Exception:
                pass
    return ImageFont.load_default()



def criar_imagem_placeholder(caminho_saida: Path, texto: str = "DESTAQUE") -> None:
    """Cria uma imagem PNG de destaque provisória com cantos arredondados."""
    caminho_saida.parent.mkdir(parents=True, exist_ok=True)
    largura, altura = 280, 80
    img = Image.new("RGBA", (largura, altura), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    draw.rounded_rectangle([(0, 0), (largura - 1, altura - 1)], radius=12, fill=(14, 165, 233, 230), outline=(255, 255, 255, 200), width=2)
    fonte = carregar_fonte(20, bold=True)
    draw.text((20, 26), texto.upper(), font=fonte, fill=(255, 255, 255, 255))
    img.save(str(caminho_saida))


def criar_video_placeholder(
    caminho_saida: Path,
    numero_cena: int,
    total_cenas: int,
    titulo: str,
    resolucao: Tuple[int, int] = (1920, 1080),
    fps: int = 30,
    duracao: float = 4.0,
) -> None:
    """Cria um vídeo MP4 placeholder de alta resolução para validação."""
    largura, altura = resolucao
    img = Image.new("RGB", (largura, altura), color=(15, 23, 42))
    draw = ImageDraw.Draw(img)

    # Faixa decorativa superior em gradiente simulado
    draw.rectangle([(0, 0), (largura, 12)], fill=(59, 130, 246))

    fonte_tag = carregar_fonte(24, bold=True)
    fonte_titulo = carregar_fonte(48, bold=True)
    fonte_sub = carregar_fonte(30)
    fonte_instrucao = carregar_fonte(22)

    margem_x = int(largura * 0.08)
    margem_y = int(altura * 0.16)
    card_box = [margem_x, margem_y, largura - margem_x, altura - margem_y]
    draw.rounded_rectangle(card_box, radius=20, fill=(30, 41, 59), outline=(51, 65, 85), width=2)

    # Tag de Passo
    tag_texto = f"PASSO {numero_cena:02d} DE {total_cenas:02d}  •  VÍDEO TUTORIAL"
    draw.text((margem_x + 50, margem_y + 50), tag_texto, font=fonte_tag, fill=(59, 130, 246))

    # Título do Passo
    draw.text((margem_x + 50, margem_y + 95), titulo, font=fonte_titulo, fill=(248, 250, 252))

    # Divisória
    draw.line(
        [(margem_x + 50, margem_y + 175), (largura - margem_x - 50, margem_y + 175)],
        fill=(71, 85, 105),
        width=2,
    )

    # Informações
    draw.text(
        (margem_x + 50, margem_y + 215),
        "Área Reservada para Gravação de Tela",
        font=fonte_sub,
        fill=(226, 232, 240),
    )
    instrucoes = (
        f"Arquivo gravado esperado: {caminho_saida.name}\n"
        f"Grave a ação da sua aplicação nesta etapa e salve o arquivo .mp4 na pasta de cenas."
    )
    draw.text((margem_x + 50, margem_y + 280), instrucoes, font=fonte_instrucao, fill=(148, 163, 184))

    caminho_saida.parent.mkdir(parents=True, exist_ok=True)
    quadro = np.array(img)
    clipe_img = ImageClip(quadro, duration=duracao).with_fps(fps)
    clipe_img.write_videofile(
        str(caminho_saida),
        fps=fps,
        codec="libx264",
        audio=False,
        logger=None,
    )
    clipe_img.close()


# ==============================================================================
# Módulo de Síntese de Voz (edge-tts)
# ==============================================================================

async def sintetizar_audio(
    texto: str,
    caminho_saida: Path,
    voz: str,
    taxa: str = "+0%",
    volume: str = "+0%",
) -> None:
    """Gera áudio neural via edge-tts."""
    caminho_saida.parent.mkdir(parents=True, exist_ok=True)
    comunicador = edge_tts.Communicate(text=texto, voice=voz, rate=taxa, volume=volume)
    await comunicador.save(str(caminho_saida))


# ==============================================================================
# Módulo de Composição Visual e Edição (MoviePy + Pillow)
# ==============================================================================

def calcular_coordenadas(
    posicao: Union[str, Tuple[int, int]],
    tamanho_elemento: Tuple[int, int],
    tamanho_video: Tuple[int, int],
    margem: int = 50,
) -> Tuple[int, int]:
    """Calcula a posição (x, y) no vídeo baseado em âncoras descritivas."""
    if isinstance(posicao, (list, tuple)):
        return (int(posicao[0]), int(posicao[1]))

    el_w, el_h = tamanho_elemento
    vid_w, vid_h = tamanho_video
    pos = str(posicao).lower().strip()

    if pos in ("inferior_esquerdo", "bottom_left"):
        return (margem, vid_h - el_h - margem)
    elif pos in ("inferior_direito", "bottom_right"):
        return (vid_w - el_w - margem, vid_h - el_h - margem)
    elif pos in ("inferior_centro", "bottom_center"):
        return ((vid_w - el_w) // 2, vid_h - el_h - margem)
    elif pos in ("superior_esquerdo", "top_left"):
        return (margem, margem)
    elif pos in ("superior_direito", "top_right"):
        return (vid_w - el_w - margem, margem)
    elif pos in ("superior_centro", "top_center"):
        return ((vid_w - el_w) // 2, margem)
    elif pos in ("centro", "center"):
        return ((vid_w - el_w) // 2, (vid_h - el_h) // 2)
    else:
        # Padrão: inferior esquerdo
        return (margem, vid_h - el_h - margem)


def gerar_overlay_texto_clip(
    cfg: OverlayTextoConfig,
    tamanho_video: Tuple[int, int],
    duracao_cena: float,
    fps: int,
) -> ImageClip:
    """Gera um clipe de texto translúcido estilo lower-third com Pillow."""
    import textwrap
    texto = cfg.texto.strip()
    fonte = carregar_fonte(30, bold=True)

    # Formata texto longo com wrap automático se necessário
    linhas_orig = texto.splitlines()
    linhas = []
    for l in linhas_orig:
        if len(l) > 55:
            linhas.extend(textwrap.wrap(l, width=55))
        else:
            linhas.append(l)
    texto_formatado = "\n".join(linhas) if linhas else texto

    pad_x, pad_y = 26, 14
    temp_img = Image.new("RGBA", (10, 10))
    temp_draw = ImageDraw.Draw(temp_img)
    bbox = temp_draw.multiline_textbbox((0, 0), texto_formatado, font=fonte, spacing=6)
    txt_w = int(math.ceil(bbox[2] - bbox[0]))
    txt_h = int(math.ceil(bbox[3] - bbox[1]))

    largura = int(txt_w + pad_x * 2 + 14)
    altura = int(txt_h + pad_y * 2)

    img = Image.new("RGBA", (largura, altura), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # Caixa com cantos arredondados translúcida elegante
    draw.rounded_rectangle(
        [(0, 0), (largura - 1, altura - 1)],
        radius=12,
        fill=(15, 23, 42, 225),
        outline=(51, 65, 85, 220),
        width=2,
    )
    # Barra lateral de acentuação azul
    draw.rounded_rectangle(
        [(4, 4), (10, altura - 5)],
        radius=3,
        fill=(59, 130, 246, 255),
    )
    # Texto renderizado (multiline suportado)
    draw.multiline_text(
        (pad_x + 8, pad_y - int(bbox[1]) + (altura - 2 * pad_y - txt_h) // 2),
        texto_formatado,
        font=fonte,
        fill=(255, 255, 255, 255),
        spacing=6,
    )

    arr = np.array(img)
    rgb = arr[:, :, :3]
    alpha = arr[:, :, 3] / 255.0

    duracao = min(cfg.duracao, duracao_cena) if cfg.duracao else duracao_cena
    clip_txt = ImageClip(rgb, duration=duracao).with_fps(fps)
    mask_clip = ImageClip(alpha, is_mask=True, duration=duracao).with_fps(fps)
    clip_txt = clip_txt.with_mask(mask_clip)

    pos_xy = calcular_coordenadas(cfg.posicao, (largura, altura), tamanho_video, margem=50)
    return clip_txt.with_position(pos_xy)


def gerar_legenda_discreta_clip(
    texto: str,
    tamanho_video: Tuple[int, int],
    duracao_cena: float,
    fps: int,
    deslocamento_y_baixo: int = 35,
) -> Optional[ImageClip]:
    """
    Gera um clipe de legenda discreta, elegante e moderna (estilo subtítulo minimalista),
    centralizada horizontalmente no rodapé com cantos arredondados e fundo translúcido escuro.
    """
    import textwrap
    texto_limpo = texto.strip()
    if not texto_limpo:
        return None

    vid_w, vid_h = tamanho_video

    # Tamanho da fonte discreto (legível sem poluir o vídeo)
    tam_fonte = 24 if vid_w >= 1600 else (20 if vid_w >= 1200 else 16)
    fonte = carregar_fonte(tam_fonte, bold=True)

    # Limita a largura do texto a ~72% da largura do vídeo
    max_txt_w = int(vid_w * 0.72)
    chars_por_linha = max(35, int(max_txt_w / (tam_fonte * 0.58)))

    linhas = []
    for paragrafo in texto_limpo.splitlines():
        if paragrafo.strip():
            linhas.extend(textwrap.wrap(paragrafo.strip(), width=chars_por_linha))
    texto_formatado = "\n".join(linhas) if linhas else texto_limpo

    pad_x, pad_y = 22, 10
    temp_img = Image.new("RGBA", (10, 10))
    temp_draw = ImageDraw.Draw(temp_img)
    bbox = temp_draw.multiline_textbbox((0, 0), texto_formatado, font=fonte, spacing=6, align="center")
    txt_w = int(math.ceil(bbox[2] - bbox[0]))
    txt_h = int(math.ceil(bbox[3] - bbox[1]))

    largura = int(txt_w + pad_x * 2)
    altura = int(txt_h + pad_y * 2)

    img = Image.new("RGBA", (largura, altura), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # Pílula translúcida suave com cantos arredondados
    draw.rounded_rectangle(
        [(0, 0), (largura - 1, altura - 1)],
        radius=10,
        fill=(10, 15, 25, 215),
        outline=(255, 255, 255, 50),
        width=1,
    )

    # Texto centralizado de alta legibilidade
    draw.multiline_text(
        (pad_x - int(bbox[0]), pad_y - int(bbox[1])),
        texto_formatado,
        font=fonte,
        fill=(255, 255, 255, 245),
        spacing=6,
        align="center",
    )

    arr = np.array(img)
    rgb = arr[:, :, :3]
    alpha = arr[:, :, 3] / 255.0

    clip_leg = ImageClip(rgb, duration=duracao_cena).with_fps(fps)
    mask_clip = ImageClip(alpha, is_mask=True, duration=duracao_cena).with_fps(fps)
    clip_leg = clip_leg.with_mask(mask_clip)

    # Posição: centralizado horizontalmente no rodapé
    pos_x = int((vid_w - largura) // 2)
    pos_y = int(vid_h - altura - deslocamento_y_baixo)
    return clip_leg.with_position((pos_x, pos_y))


def gerar_imagem_destaque_clip(
    cfg: ImagemDestaqueConfig,
    tamanho_video: Tuple[int, int],
    duracao_cena: float,
    fps: int,
) -> ImageClip:
    """Carrega, redimensiona proporcionalmente e posiciona imagem de destaque."""
    img_orig = Image.open(cfg.caminho).convert("RGBA")

    # Redimensiona proporcionalmente mantendo aspecto
    max_w, max_h = cfg.tamanho_max
    img_orig.thumbnail((max_w, max_h), Image.Resampling.LANCZOS)
    largura, altura = img_orig.size

    arr = np.array(img_orig)
    rgb = arr[:, :, :3]
    alpha = arr[:, :, 3] / 255.0

    duracao = min(cfg.duracao, duracao_cena) if cfg.duracao else duracao_cena
    clip_img = ImageClip(rgb, duration=duracao).with_fps(fps)
    mask_clip = ImageClip(alpha, is_mask=True, duration=duracao).with_fps(fps)
    clip_img = clip_img.with_mask(mask_clip)

    pos_xy = calcular_coordenadas(cfg.posicao, (largura, altura), tamanho_video, margem=50)
    return clip_img.with_position(pos_xy)


def padronizar_resolucao(
    clip: VideoFileClip,
    resolucao_alvo: Tuple[int, int] = (1920, 1080),
    fps_alvo: int = 30,
) -> VideoFileClip:
    """
    Padroniza resolução para um valor exato (ex: 1920x1080) sem distorcer proporções.
    Se a proporção for diferente, ajusta e centraliza sobre um fundo preto limpo.
    """
    target_w, target_h = resolucao_alvo
    fps_atual = clip.fps if clip.fps else fps_alvo
    clip = clip.with_fps(fps_atual)

    if clip.size == [target_w, target_h]:
        return clip

    # Calcula escala proporcional mantendo aspecto
    escala = min(target_w / clip.w, target_h / clip.h)
    new_w = int(round(clip.w * escala))
    new_h = int(round(clip.h * escala))

    clip_redimensionado = clip.with_effects([vfx.Resize(new_size=(new_w, new_h))])

    if clip_redimensionado.size == [target_w, target_h]:
        return clip_redimensionado

    # Cria fundo na resolução exata e centraliza o clipe original
    fundo = ColorClip(size=(target_w, target_h), color=(0, 0, 0), duration=clip_redimensionado.duration).with_fps(fps_atual)
    clip_padronizado = CompositeVideoClip(
        [fundo, clip_redimensionado.with_position(("center", "center"))],
        size=(target_w, target_h),
    )
    return clip_padronizado


def processar_cena_individual(
    cena: Cena,
    caminho_audio: Path,
    config_geral: ConfiguracaoGeral,
) -> VideoFileClip:
    """
    Processa um único passo/cena do tutorial:
    1. Abre vídeo bruto ou imagem de captura de tela, e áudio sintetizado.
    2. Sincroniza durações (se imagem, dura o tempo do áudio + pausa; se vídeo, congela quadro final se necessário).
    3. Padroniza resolução (evitando problemas na concatenação).
    4. Aplica camadas de texto e imagem de destaque.
    5. Retorna o clipe pronto com áudio embutido.
    """
    clip_audio = AudioFileClip(str(caminho_audio))
    pausa = cena.pausa_final if cena.pausa_final is not None else config_geral.pausa_final_padrao
    duracao_audio_com_pausa = clip_audio.duration + max(0.0, pausa)

    ext = cena.video_path.suffix.lower()
    is_image = ext in [".png", ".jpg", ".jpeg", ".webp", ".bmp"]

    if is_image:
        fps = config_geral.fps_padrao
        # Carrega a captura de tela estática durando exatamente o tempo da narração
        clip_base = ImageClip(str(cena.video_path), duration=duracao_audio_com_pausa).with_fps(fps)
        clip_video = padronizar_resolucao(
            clip_base,
            resolucao_alvo=config_geral.resolucao_padrao,
            fps_alvo=fps,
        )
    else:
        clip_video = VideoFileClip(str(cena.video_path))
        fps = clip_video.fps if clip_video.fps else config_geral.fps_padrao
        clip_video = clip_video.with_fps(fps)

        # Sincronização inteligente: congelar último frame se áudio for maior
        if clip_video.duration < duracao_audio_com_pausa:
            congelamento = duracao_audio_com_pausa - clip_video.duration
            clip_video = clip_video.with_effects([vfx.Freeze(t="end", freeze_duration=congelamento)])

        # Padronização de resolução
        clip_video = padronizar_resolucao(
            clip_video,
            resolucao_alvo=config_geral.resolucao_padrao,
            fps_alvo=config_geral.fps_padrao,
        )

    # Camadas de overlay (tarja visual, legenda discreta e imagem de destaque)
    camadas = [clip_video]
    tem_overlay_inferior = False
    if cena.overlay_texto:
        clip_txt = gerar_overlay_texto_clip(
            cfg=cena.overlay_texto,
            tamanho_video=config_geral.resolucao_padrao,
            duracao_cena=clip_video.duration,
            fps=config_geral.fps_padrao,
        )
        camadas.append(clip_txt)
        pos = str(cena.overlay_texto.posicao).lower().strip()
        if "inferior" in pos or "bottom" in pos:
            tem_overlay_inferior = True

    if cena.legenda and str(cena.legenda).strip() and getattr(cena, "exibir_legenda", True):
        clip_leg = gerar_legenda_discreta_clip(
            texto=str(cena.legenda).strip(),
            tamanho_video=config_geral.resolucao_padrao,
            duracao_cena=clip_video.duration,
            fps=config_geral.fps_padrao,
            deslocamento_y_baixo=130 if tem_overlay_inferior else 35,
        )
        if clip_leg is not None:
            camadas.append(clip_leg)

    if cena.imagem_destaque:
        clip_img = gerar_imagem_destaque_clip(
            cfg=cena.imagem_destaque,
            tamanho_video=config_geral.resolucao_padrao,
            duracao_cena=clip_video.duration,
            fps=config_geral.fps_padrao,
        )
        camadas.append(clip_img)

    if len(camadas) > 1:
        clip_composto = CompositeVideoClip(camadas, size=config_geral.resolucao_padrao)
    else:
        clip_composto = clip_video

    # Atribui o áudio sintetizado
    clip_final = clip_composto.with_audio(clip_audio)
    return clip_final


# ==============================================================================
# Orquestrador Principal do Gerador Genérico
# ==============================================================================

async def executar_gerador_generico(
    caminho_config: Path,
    caminho_saida_override: Optional[Path] = None,
    voz_override: Optional[str] = None,
    taxa_override: Optional[str] = None,
    gerar_placeholders: bool = False,
    manter_audios: bool = False,
) -> Path:
    """Executa a compilação completa do vídeo tutorial data-driven."""
    print("=" * 75)
    print("🚀 MOTOR DE AUTOMAÇÃO DE VÍDEOS TUTORIAIS (GERADOR GENÉRICO)")
    print("=" * 75)

    titulo_tutorial, config_geral, cenas = carregar_configuracao(caminho_config)

    # Aplica overrides passados via linha de comando
    if caminho_saida_override:
        config_geral.video_saida = caminho_saida_override
    if voz_override:
        config_geral.voz_padrao = voz_override
    if taxa_override:
        config_geral.taxa_fala_padrao = taxa_override
    if manter_audios:
        config_geral.manter_audios_temp = True

    config_geral.video_saida.parent.mkdir(parents=True, exist_ok=True)
    pasta_audios = Path("audios_temp")
    pasta_audios.mkdir(parents=True, exist_ok=True)

    print(f"📌 Tutorial: {titulo_tutorial}")
    print(f"⚙️  Arquivo de Configuração: {caminho_config}")
    print(f"🎙️  Voz Padrão: {config_geral.voz_padrao} (Velocidade: {config_geral.taxa_fala_padrao})")
    print(f"📺 Resolução Padronizada: {config_geral.resolucao_padrao[0]}x{config_geral.resolucao_padrao[1]} @ {config_geral.fps_padrao}fps")
    print(f"📑 Total de Passos/Cenas: {len(cenas)}")
    print(f"💾 Destino do Vídeo Final: {config_geral.video_saida}")
    print("-" * 75)

    # 1. Validação Pré-Voo e Tratamento de Erros
    validar_arquivos(
        cenas=cenas,
        resolucao=config_geral.resolucao_padrao,
        fps=config_geral.fps_padrao,
        gerar_placeholders=gerar_placeholders,
    )

    # 2. Geração de Áudios Neurais via edge-tts
    print("\n[ETAPA 1/3] Sintetizando áudios de narração...")
    arquivos_audio: List[Path] = []
    for i, cena in enumerate(cenas, 1):
        caminho_audio = pasta_audios / f"{cena.id}_{i:02d}.mp3"
        arquivos_audio.append(caminho_audio)

        voz_cena = voz_override if voz_override else (cena.voz or config_geral.voz_padrao)
        taxa_cena = taxa_override if taxa_override else (cena.taxa_fala or config_geral.taxa_fala_padrao)

        print(f"   🔊 [{i:02d}/{len(cenas):02d}] Narrando '{cena.titulo}' (Voz: {voz_cena})...")
        await sintetizar_audio(
            texto=cena.texto_narracao,
            caminho_saida=caminho_audio,
            voz=voz_cena,
            taxa=taxa_cena,
            volume=config_geral.volume_padrao,
        )

    # 3. Processamento Individual e Sincronização
    print("\n[ETAPA 2/3] Sincronizando vídeo, áudio e aplicando overlays visuais...")
    clipes_prontos: List[VideoFileClip] = []
    try:
        for i, (cena, arq_audio) in enumerate(zip(cenas, arquivos_audio), 1):
            print(f"   🎞️  [{i:02d}/{len(cenas):02d}] Processando cena '{cena.titulo}' ({cena.video_path.name})...")
            clipe = processar_cena_individual(
                cena=cena,
                caminho_audio=arq_audio,
                config_geral=config_geral,
            )
            print(f"       -> Duração final ajustada: {clipe.duration:.2f}s")
            clipes_prontos.append(clipe)

        # 4. Concatenação e Renderização do Vídeo Final
        print(f"\n[ETAPA 3/3] Concatenando {len(clipes_prontos)} cenas e renderizando vídeo final...")
        video_completo = concatenate_videoclips(clipes_prontos, method="compose")
        duracao_total = video_completo.duration
        minutos = int(duracao_total // 60)
        segundos = int(duracao_total % 60)

        print(f"   ⏱️  Duração total calculada: {minutos}m {segundos}s ({duracao_total:.2f}s)")
        print(f"   🎬 Codificando vídeo em: {config_geral.video_saida}...")

        video_completo.write_videofile(
            str(config_geral.video_saida),
            fps=config_geral.fps_padrao,
            codec="libx264",
            audio_codec="aac",
            preset="medium",
            threads=8,
        )
        video_completo.close()

    finally:
        # Liberação de recursos e descritores de arquivos
        for clp in clipes_prontos:
            try:
                clp.close()
            except Exception:
                pass

        # Limpeza de áudios se não configurado para manter
        if not config_geral.manter_audios_temp:
            for arq in arquivos_audio:
                try:
                    if arq.is_file():
                        arq.unlink()
                except Exception:
                    pass
            try:
                pasta_audios.rmdir()
            except Exception:
                pass

    print("\n" + "=" * 75)
    print("🎉 VÍDEO TUTORIAL COMPILADO COM SUCESSO!")
    print(f"📂 Arquivo Gerado: {config_geral.video_saida.resolve()}")
    print("=" * 75)
    return config_geral.video_saida


async def listar_vozes_edge() -> None:
    """Lista as vozes em português brasileiro do edge-tts."""
    vozes = await edge_tts.list_voices()
    vozes_pt_br = [v for v in vozes if v["Locale"].startswith("pt-BR")]
    print("\n🎙️  Vozes neurais disponíveis em Português Brasileiro (pt-BR):")
    print("-" * 65)
    print(f"{'Nome da Voz':<35} {'Gênero':<10} {'Estilos':<20}")
    print("-" * 65)
    for v in vozes_pt_br:
        genero = v.get("Gender", "N/A")
        estilos = ", ".join(v.get("VoicePersonalities", [])) or "Padrão"
        print(f"{v['ShortName']:<35} {genero:<10} {estilos:<20}")
    print("-" * 65)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Gerador Genérico de Vídeos Tutoriais com IA (edge-tts + MoviePy)"
    )
    parser.add_argument(
        "-c",
        "--config",
        type=Path,
        default=None,
        help="Caminho para o JSON de configuração (padrão: config_projeto.json)",
    )
    parser.add_argument(
        "-o",
        "--saida",
        type=Path,
        default=None,
        help="Caminho do vídeo de saída (sobrescreve o JSON de configuração)",
    )
    parser.add_argument(
        "-v",
        "--voz",
        type=str,
        default=None,
        help="Voz padrão do edge-tts (ex: pt-BR-AntonioNeural, pt-BR-FranciscaNeural)",
    )
    parser.add_argument(
        "-t",
        "--taxa",
        type=str,
        default=None,
        help="Ajuste de velocidade da narração (ex: +10%%, -5%%)",
    )
    parser.add_argument(
        "--gerar-placeholders",
        action="store_true",
        help="Cria mídias provisórias (placeholders) para vídeos ou imagens ausentes",
    )
    parser.add_argument(
        "--manter-audios",
        action="store_true",
        help="Preserva arquivos de áudio temporários na pasta 'audios_temp/'",
    )
    parser.add_argument(
        "--listar-vozes",
        action="store_true",
        help="Lista todas as vozes neurais pt-BR disponíveis e finaliza",
    )

    args = parser.parse_args()

    if args.listar_vozes:
        asyncio.run(listar_vozes_edge())
        return

    # Determina arquivo de configuração padrão
    caminho_cfg = args.config
    if caminho_cfg is None:
        if Path("config_projeto.json").is_file():
            caminho_cfg = Path("config_projeto.json")
        elif Path("config_exemplo.json").is_file():
            caminho_cfg = Path("config_exemplo.json")
        else:
            caminho_cfg = Path("config_projeto.json")

    asyncio.run(
        executar_gerador_generico(
            caminho_config=caminho_cfg,
            caminho_saida_override=args.saida,
            voz_override=args.voz,
            taxa_override=args.taxa,
            gerar_placeholders=args.gerar_placeholders,
            manter_audios=args.manter_audios,
        )
    )


if __name__ == "__main__":
    main()
