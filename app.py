#!/usr/bin/env python3
"""
app.py
======
Interface Web Moderna e Intuitiva com Streamlit para o Gerador Genérico de Vídeos Tutoriais.
Permite configurar o projeto, gerenciar cenas dinamicamente (upload de vídeo + narração),
acompanhar o progresso da síntese de voz (edge-tts) e renderização (MoviePy),
e assistir/baixar o vídeo final gerado.
"""

import asyncio
import concurrent.futures
import importlib
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

import streamlit as st
from PIL import Image, ImageDraw
from moviepy import (
    AudioFileClip,
    CompositeVideoClip,
    ImageClip,
    VideoFileClip,
    concatenate_videoclips,
    vfx,
)

# Força recarga do módulo gerador_generico para garantir código atualizado
import gerador_generico
importlib.reload(gerador_generico)

from gerador_generico import (
    Cena,
    ConfiguracaoGeral,
    OverlayTextoConfig,
    carregar_fonte,
    gerar_imagem_destaque_clip,
    gerar_legenda_discreta_clip,
    gerar_overlay_texto_clip,
    padronizar_resolucao,
    processar_cena_individual,
    sintetizar_audio,
)

# ==============================================================================
# Configurações da Página do Streamlit
# ==============================================================================
st.set_page_config(
    page_title="Gerador de Vídeos Tutoriais IA",
    page_icon="🎬",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ==============================================================================
# Estilização CSS Personalizada (Modern & Clean)
# ==============================================================================
st.markdown(
    """
    <style>
    /* Estilos gerais */
    .main-title {
        font-size: 2.2rem;
        font-weight: 700;
        margin-bottom: 0.2rem;
        background: linear-gradient(90deg, #3b82f6, #8b5cf6);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
    }
    .subtitle {
        color: #94a3b8;
        font-size: 1rem;
        margin-bottom: 1.5rem;
    }
    .scene-card {
        background-color: #1e293b;
        border-radius: 10px;
        padding: 1.2rem;
        margin-bottom: 1rem;
        border: 1px solid #334155;
    }
    .badge {
        display: inline-block;
        padding: 0.25rem 0.6rem;
        font-size: 0.8rem;
        font-weight: 600;
        border-radius: 6px;
        background-color: #0284c7;
        color: #f8fafc;
        margin-bottom: 0.5rem;
    }
    .stButton>button {
        border-radius: 8px;
        font-weight: 600;
        transition: all 0.2s ease-in-out;
    }
    .stButton>button:hover {
        transform: translateY(-1px);
    }
    </style>
    """,
    unsafe_allow_html=True,
)

# ==============================================================================
# Funções Auxiliares
# ==============================================================================

def sanitizar_nome_arquivo(nome: str) -> str:
    """Gera um nome de arquivo seguro a partir do título."""
    # Remove acentuações e caracteres especiais
    nfkd = unicodedata.normalize("NFKD", nome)
    nome_sem_acento = "".join([c for c in nfkd if not unicodedata.combining(c)])
    nome_limpo = re.sub(r"[^\w\s-]", "", nome_sem_acento).strip().lower()
    nome_limpo = re.sub(r"[-\s]+", "_", nome_limpo)
    return nome_limpo or "tutorial_final"


def executar_assincrono(coro):
    """Executa corrotina assíncrona em uma thread dedicada e segura."""
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
        return executor.submit(lambda: asyncio.run(coro)).result()


def obter_caminho_vtt_legenda(uid: str, texto: str) -> Optional[str]:
    """Gera arquivo WebVTT para exibir legenda nativa sincronizada no player do Streamlit."""
    t = texto.strip()
    if not t:
        return None
    pasta_vtt = Path("temp_streamlit/vtt")
    pasta_vtt.mkdir(parents=True, exist_ok=True)
    arq_vtt = pasta_vtt / f"legenda_{uid}.vtt"
    linhas = [l.strip() for l in t.splitlines() if l.strip()]
    corpo = "\n".join(linhas)
    conteudo = f"WEBVTT\n\n00:00:00.000 --> 01:00:00.000\n{corpo}\n"
    arq_vtt.write_text(conteudo, encoding="utf-8")
    return str(arq_vtt)


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
        d_tarja.rounded_rectangle([(0, 0), (lw - 1, lh - 1)], radius=12, fill=(15, 23, 42, 225), outline=(51, 65, 85, 220), width=2)
        d_tarja.rounded_rectangle([(4, 4), (10, lh - 5)], radius=3, fill=(59, 130, 246, 255))
        d_tarja.multiline_text((pad_x + 8, pad_y - int(bb[1]) + (lh - 2 * pad_y - th) // 2), txt_fmt, font=fonte_tarja, fill=(255, 255, 255, 255), spacing=6)
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
        d_leg.rounded_rectangle([(0, 0), (lw - 1, lh - 1)], radius=10, fill=(10, 15, 25, 215), outline=(255, 255, 255, 50), width=1)
        d_leg.multiline_text((pad_x - int(bb[0]), pad_y - int(bb[1])), txt_fmt, font=fonte_leg, fill=(255, 255, 255, 245), spacing=6, align="center")
        desloc = 130 if tem_tarja_inferior else 35
        base.paste(leg_img, ((vid_w - lw) // 2, vid_h - lh - desloc), leg_img)

    return base.convert("RGB")



# ==============================================================================
# Configurações Globais e Constantes
# ==============================================================================

PASTA_TEMP_IMPORTACAO = Path("temp_streamlit/projeto_importado")
PASTA_TEMP_IMPORTACAO.mkdir(parents=True, exist_ok=True)

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
    "Vertical Shorts/Reels 1080x1920": (1080, 1920),
}

TAXAS_FALA = ["-20%", "-10%", "+0%", "+10%", "+20%", "+30%"]


# ==============================================================================
# Funções de Gerenciamento e Persistência de Projetos
# ==============================================================================

def coletar_cenas_atuais() -> List[Dict[str, Any]]:
    """Coleta o estado atual de todas as cenas a partir do session_state."""
    cenas = []
    for idx, c in enumerate(st.session_state.get("scenes", []), 1):
        uid = c["uid"]
        titulo = st.session_state.get(f"titulo_{uid}", c.get("titulo", f"Passo {idx:02d}"))
        tarja = st.session_state.get(f"tarja_{uid}", c.get("tarja_visual", c.get("overlay_texto", titulo)))
        legenda = st.session_state.get(f"legenda_{uid}", c.get("legenda", ""))
        usar_legenda = st.session_state.get(f"usar_legenda_fala_{uid}", c.get("usar_legenda_fala", True))

        if usar_legenda and str(legenda).strip():
            narracao = str(legenda).strip()
        else:
            narracao = st.session_state.get(f"narracao_{uid}", c.get("narracao", ""))

        overlay = st.session_state.get(f"overlay_{uid}", c.get("exibir_overlay", True))
        exibir_legenda = st.session_state.get(f"exibir_legenda_{uid}", c.get("exibir_legenda", True))
        upload_obj = st.session_state.get(f"upload_{uid}")
        caminho_disco = c.get("caminho_midia")
        cenas.append({
            "numero": idx,
            "id": f"cena_{idx:02d}",
            "uid": uid,
            "titulo": str(titulo).strip() if titulo else f"Passo {idx:02d}",
            "tarja_visual": str(tarja).strip() if tarja else (str(titulo).strip() if titulo else f"Passo {idx:02d}"),
            "narracao": str(narracao).strip() if narracao else "",
            "legenda": str(legenda).strip() if legenda else "",
            "usar_legenda_fala": bool(usar_legenda),
            "exibir_overlay": bool(overlay),
            "exibir_legenda": bool(exibir_legenda),
            "upload_obj": upload_obj,
            "caminho_disco": caminho_disco,
        })
    return cenas


def obter_configuracoes_gerais_atuais() -> Tuple[str, str, Tuple[int, int], int, float]:
    """Retorna a tupla (voz_short, taxa, resolucao_tuple, fps, pausa) atuais."""
    cfg_resolucao = st.session_state.get("cfg_resolucao", list(OPCOES_RESOLUCAO.keys())[0])
    resolucao = OPCOES_RESOLUCAO.get(cfg_resolucao, (1920, 1080))
    voz_label = st.session_state.get("cfg_voz_label", list(OPCOES_VOZES.keys())[0])
    voz_short = (
        st.session_state.get("cfg_voz_custom", "pt-BR-AntonioNeural")
        if OPCOES_VOZES.get(voz_label) == "custom"
        else OPCOES_VOZES.get(voz_label, "pt-BR-AntonioNeural")
    )
    taxa = st.session_state.get("cfg_taxa_fala", "+0%")
    fps = int(st.session_state.get("cfg_fps", 30))
    pausa = float(st.session_state.get("cfg_pausa", 0.5))
    return voz_short, taxa, resolucao, fps, pausa


def resolver_caminho_midia(
    caminho: Optional[Any],
    pasta_contexto: Optional[Path] = None,
) -> Optional[Path]:
    """
    Localiza o arquivo de mídia (vídeo ou imagem) de forma flexível:
    1. Caminho direto relativo ou absoluto.
    2. Relativo à pasta_contexto (ex: pasta do projeto).
    3. Relativo a pasta_contexto / midias/.
    4. Relativo a pasta_contexto / p.name.
    5. Dentro das pastas conhecidas: imgs/, cenas/, projetos/, temp_streamlit/.
    """
    if not caminho:
        return None
    p = Path(str(caminho).strip())
    if not str(p) or str(p) in [".", "/"]:
        return None

    # 1. Caminho direto
    if p.is_file():
        return p

    # 2. Relativo à pasta de contexto
    if pasta_contexto:
        if (pasta_contexto / p).is_file():
            return pasta_contexto / p
        if (pasta_contexto / "midias" / p.name).is_file():
            return pasta_contexto / "midias" / p.name
        if (pasta_contexto / p.name).is_file():
            return pasta_contexto / p.name

    # 3. Busca nas pastas conhecidas
    for sub in ["imgs", "cenas", "temp_streamlit"]:
        candidato = Path(sub) / p.name
        if candidato.is_file():
            return candidato
        if Path(sub).is_dir():
            for achado in Path(sub).glob(f"**/{p.name}"):
                if achado.is_file():
                    return achado

    return None


def gerar_json_projeto_atual() -> Tuple[str, str]:
    """Gera string JSON e nome de arquivo para download do projeto atual."""
    titulo = st.session_state.get("input_titulo_projeto", "Meu Tutorial").strip() or "tutorial"
    slug = sanitizar_nome_arquivo(titulo)
    voz_short, taxa, resolucao, fps, pausa = obter_configuracoes_gerais_atuais()
    cenas_coletadas = coletar_cenas_atuais()

    cenas_json = []
    for c in cenas_coletadas:
        midia = c["caminho_disco"] or (c["upload_obj"].name if c["upload_obj"] else "")
        texto_tarja = c["tarja_visual"] if c.get("tarja_visual") else c["titulo"]
        overlay_val = texto_tarja if (c["exibir_overlay"] and texto_tarja) else None
        cenas_json.append({
            "id": c["id"],
            "titulo": c["titulo"],
            "tarja_visual": c.get("tarja_visual", texto_tarja),
            "video_path": midia,
            "texto_narracao": c["narracao"],
            "legenda": c["legenda"],
            "usar_legenda_fala": c.get("usar_legenda_fala", True),
            "exibir_legenda": c.get("exibir_legenda", True),
            "voz": voz_short,
            "taxa_fala": taxa,
            "overlay_texto": overlay_val,
            "pausa_final": pausa,
        })

    dados = {
        "titulo_tutorial": titulo,
        "configuracoes_gerais": {
            "voz_padrao": voz_short,
            "taxa_fala_padrao": taxa,
            "volume_padrao": "+0%",
            "resolucao_padrao": [resolucao[0], resolucao[1]],
            "fps_padrao": fps,
            "pausa_final_padrao": pausa,
            "video_saida": f"saida/{slug}.mp4",
            "manter_audios_temp": False,
        },
        "cenas": cenas_json,
    }
    return json.dumps(dados, ensure_ascii=False, indent=2), f"{slug}.json"


def gerar_zip_projeto_atual() -> Tuple[bytes, str]:
    """
    Gera um pacote ZIP autossuficiente contendo projeto.json e
    todas as mídias (fotos e vídeos) de todas as cenas na pasta midias/.
    Não armazena arquivos no servidor; o ZIP é gerado em memória para download.
    """
    titulo = st.session_state.get("input_titulo_projeto", "Meu Tutorial").strip() or "tutorial"
    slug = sanitizar_nome_arquivo(titulo)
    voz_short, taxa, resolucao, fps, pausa = obter_configuracoes_gerais_atuais()
    cenas_coletadas = coletar_cenas_atuais()

    buffer_zip = io.BytesIO()
    with zipfile.ZipFile(buffer_zip, "w", zipfile.ZIP_DEFLATED) as zf:
        cenas_json = []
        for idx, c in enumerate(cenas_coletadas):
            id_cena = c["id"]
            caminho_midia_no_zip = ""

            # 1. Se houver upload recente no widget
            if c["upload_obj"] is not None:
                ext = Path(c["upload_obj"].name).suffix.lower() or ".mp4"
                stem_orig = sanitizar_nome_arquivo(Path(c["upload_obj"].name).stem)
                if stem_orig.startswith(f"{id_cena}_"):
                    stem_orig = stem_orig[len(f"{id_cena}_"):]
                nome_arq_midia = f"{id_cena}_{stem_orig}{ext}"
                caminho_midia_no_zip = f"midias/{nome_arq_midia}"
                zf.writestr(caminho_midia_no_zip, c["upload_obj"].getvalue())
            # 2. Se houver mídia no disco
            else:
                orig = resolver_caminho_midia(c["caminho_disco"])
                if orig and orig.is_file():
                    ext = orig.suffix.lower() or ".png"
                    stem_orig = orig.stem
                    if stem_orig.startswith(f"{id_cena}_"):
                        stem_orig = stem_orig[len(f"{id_cena}_"):]
                    nome_limpo_orig = sanitizar_nome_arquivo(stem_orig) + ext
                    nome_arq_midia = f"{id_cena}_{nome_limpo_orig}"
                    caminho_midia_no_zip = f"midias/{nome_arq_midia}"
                    try:
                        with open(orig, "rb") as f_orig:
                            zf.writestr(caminho_midia_no_zip, f_orig.read())
                    except Exception:
                        caminho_midia_no_zip = str(orig)
                else:
                    caminho_midia_no_zip = c.get("caminho_disco") or ""

            texto_tarja = c["tarja_visual"] if c.get("tarja_visual") else c["titulo"]
            overlay_val = texto_tarja if (c["exibir_overlay"] and texto_tarja) else None
            cenas_json.append({
                "id": id_cena,
                "titulo": c["titulo"],
                "tarja_visual": c.get("tarja_visual", texto_tarja),
                "video_path": caminho_midia_no_zip,
                "texto_narracao": c["narracao"],
                "legenda": c["legenda"],
                "usar_legenda_fala": c.get("usar_legenda_fala", True),
                "exibir_legenda": c.get("exibir_legenda", True),
                "voz": voz_short,
                "taxa_fala": taxa,
                "overlay_texto": overlay_val,
                "pausa_final": pausa,
            })

        dados_projeto = {
            "titulo_tutorial": titulo,
            "configuracoes_gerais": {
                "voz_padrao": voz_short,
                "taxa_fala_padrao": taxa,
                "volume_padrao": "+0%",
                "resolucao_padrao": [resolucao[0], resolucao[1]],
                "fps_padrao": fps,
                "pausa_final_padrao": pausa,
                "video_saida": f"saida/{slug}.mp4",
                "manter_audios_temp": False,
            },
            "cenas": cenas_json,
        }

        json_str = json.dumps(dados_projeto, ensure_ascii=False, indent=2)
        zf.writestr("projeto.json", json_str.encode("utf-8"))

    buffer_zip.seek(0)
    return buffer_zip.getvalue(), f"{slug}.zip"


def descompactar_e_restaurar_zip(arquivo_zip_bytes: bytes, nome_arquivo_original: str) -> bool:
    """
    Descompacta um arquivo ZIP contendo o projeto para projetos/<slug>/,
    extrai o projeto.json e as mídias, atualiza os caminhos e agenda a restauração.
    """
    try:
        buffer_zip = io.BytesIO(arquivo_zip_bytes)
        with zipfile.ZipFile(buffer_zip, "r") as zf:
            nomes_arquivos = zf.namelist()

            # Encontra o arquivo projeto.json ou qualquer arquivo .json
            arq_json = None
            for nome in nomes_arquivos:
                if Path(nome).name == "projeto.json":
                    arq_json = nome
                    break
            if not arq_json:
                for nome in nomes_arquivos:
                    if nome.endswith(".json") and not Path(nome).name.startswith("."):
                        arq_json = nome
                        break

            if not arq_json:
                st.error("❌ Nenhum arquivo de configuração (.json) encontrado dentro do pacote .zip.")
                return False

            # Lê os dados do JSON para saber o nome do projeto
            conteudo_json = zf.read(arq_json).decode("utf-8")
            dados = json.loads(conteudo_json)
            titulo = dados.get("titulo_tutorial", dados.get("titulo", Path(nome_arquivo_original).stem))
            slug = sanitizar_nome_arquivo(titulo)

            # Pasta temporária de trabalho da sessão (sem armazenamento permanente no servidor)
            pasta_destino = Path("temp_streamlit/projeto_importado")
            if pasta_destino.exists():
                shutil.rmtree(pasta_destino, ignore_errors=True)
            pasta_destino.mkdir(parents=True, exist_ok=True)

            # Detecta se há uma pasta raiz no zip para remover o prefixo
            prefixo_raiz = ""
            if "/" in arq_json:
                partes = arq_json.split("/")
                if len(partes) > 1 and partes[0]:
                    prefixo_raiz = partes[0] + "/"

            # Extração segura dos arquivos
            for membro in zf.infolist():
                nome_rel = membro.filename
                if prefixo_raiz and nome_rel.startswith(prefixo_raiz):
                    nome_rel = nome_rel[len(prefixo_raiz):]

                if not nome_rel or nome_rel.endswith("/"):
                    continue
                if Path(nome_rel).name.startswith(".") or "__MACOSX" in nome_rel:
                    continue

                caminho_final = (pasta_destino / nome_rel).resolve()
                if not caminho_final.is_relative_to(pasta_destino.resolve()):
                    continue

                caminho_final.parent.mkdir(parents=True, exist_ok=True)
                with open(caminho_final, "wb") as f_out:
                    f_out.write(zf.read(membro.filename))

            # Atualiza os caminhos das mídias no JSON para apontar para a pasta extraída
            caminho_json_extraido = pasta_destino / "projeto.json"
            for c in (dados.get("cenas") or dados.get("passos") or []):
                midia_rel = (
                    c.get("video_path")
                    or c.get("video")
                    or c.get("imagem_path")
                    or c.get("imagem")
                    or c.get("captura_tela")
                    or c.get("midia_path")
                    or ""
                )
                if midia_rel:
                    candidato = resolver_caminho_midia(midia_rel, pasta_destino)
                    if candidato and candidato.is_file():
                        c["video_path"] = str(candidato)

            # Salva o projeto.json temporário para a sessão ativa
            with open(caminho_json_extraido, "w", encoding="utf-8") as f_j:
                json.dump(dados, f_j, ensure_ascii=False, indent=2)

            restaurar_projeto_de_dados(dados, caminho_json_extraido)
            return True

    except Exception as e:
        st.error(f"Erro ao descompactar e carregar projeto: {e}")
        return False


def limpar_todos_arquivos_temporarios(remover_videos_saida: bool = True, manter_caminho: Optional[str] = None) -> int:
    """
    Remove todos os arquivos temporários criados pela aplicação:
    - Pasta temp_streamlit/ (previews de áudio, legendas vtt, uploads temporários, extrações zip).
    - Pasta scratch/ (se existir).
    - Arquivos .mp4 na pasta saida/ (se remover_videos_saida=True, exceto manter_caminho).
    Retorna o número total de arquivos e diretórios removidos.
    """
    removidos = 0

    # 1. Limpeza de temp_streamlit/
    pasta_temp = Path("temp_streamlit")
    if pasta_temp.is_dir():
        for item in pasta_temp.iterdir():
            try:
                if item.is_file():
                    item.unlink(missing_ok=True)
                    removidos += 1
                elif item.is_dir():
                    shutil.rmtree(item, ignore_errors=True)
                    removidos += 1
            except Exception:
                pass

    # 2. Limpeza de scratch/
    pasta_scratch = Path("scratch")
    if pasta_scratch.is_dir():
        try:
            shutil.rmtree(pasta_scratch, ignore_errors=True)
            removidos += 1
        except Exception:
            pass

    # 3. Limpeza de vídeos gerados em saida/
    if remover_videos_saida:
        pasta_saida = Path("saida")
        if pasta_saida.is_dir():
            for f in pasta_saida.glob("*.mp4"):
                if manter_caminho and str(f.resolve()) == str(Path(manter_caminho).resolve()):
                    continue
                try:
                    f.unlink(missing_ok=True)
                    removidos += 1
                except Exception:
                    pass

    return removidos


def listar_modelos_disponiveis() -> List[Dict[str, Any]]:
    """Lista modelos de exemplo pré-configurados no repositório."""
    modelos = []

    p_exemplo = Path("config_exemplo.json")
    if p_exemplo.is_file():
        modelos.append({
            "nome_exibicao": "⭐ Modelo 1: Exemplo Básico Multi-Cenas (3 Cenas em Vídeo - cenas/)",
            "caminho_arquivo": p_exemplo,
        })

    p_projeto = Path("config_projeto.json")
    if p_projeto.is_file():
        modelos.append({
            "nome_exibicao": "🎓 Modelo 2: Tutorial Completo AVA Moodle PGDP UEFS (26 Cenas em Imagens - imgs/)",
            "caminho_arquivo": p_projeto,
        })

    return modelos


def executar_restauracao_projeto(dados: dict, caminho_origem: Optional[Path] = None):
    """
    Restaura um projeto a partir de dados JSON (dicionário),
    atualizando todas as configurações globais e cenas no session_state.
    Executado no topo do script antes da instanciação de qualquer widget.
    """
    cenas_raw = dados.get("cenas") or dados.get("passos") or []
    if not isinstance(cenas_raw, list) or len(cenas_raw) == 0:
        return

    # 1. Limpar chaves antigas de cena do session_state
    for c in st.session_state.get("scenes", []):
        uid = c.get("uid")
        if uid:
            st.session_state.pop(f"titulo_{uid}", None)
            st.session_state.pop(f"narracao_{uid}", None)
            st.session_state.pop(f"overlay_{uid}", None)
            st.session_state.pop(f"audio_preview_{uid}", None)

    # 2. Restaurar título
    titulo = dados.get("titulo_tutorial", dados.get("titulo", "Meu Vídeo Tutorial"))
    st.session_state["input_titulo_projeto"] = titulo

    # 3. Restaurar configurações gerais
    cfg_geral = dados.get("configuracoes_gerais", dados.get("configuracoes", {}))

    # Voz
    voz_salva = cfg_geral.get("voz_padrao", cfg_geral.get("voz", "pt-BR-AntonioNeural"))
    voz_encontrada = False
    for label, shortname in OPCOES_VOZES.items():
        if shortname == voz_salva:
            st.session_state["cfg_voz_label"] = label
            voz_encontrada = True
            break
    if not voz_encontrada:
        st.session_state["cfg_voz_label"] = "Outra voz personalizada"
        st.session_state["cfg_voz_custom"] = voz_salva

    # Taxa de fala
    taxa_salva = cfg_geral.get("taxa_fala_padrao", cfg_geral.get("taxa_fala", "+0%"))
    if taxa_salva in TAXAS_FALA:
        st.session_state["cfg_taxa_fala"] = taxa_salva

    # Resolução
    res_salva = cfg_geral.get("resolucao_padrao", [1920, 1080])
    if isinstance(res_salva, (list, tuple)) and len(res_salva) == 2:
        res_tuple = (int(res_salva[0]), int(res_salva[1]))
        for label, val_tuple in OPCOES_RESOLUCAO.items():
            if val_tuple == res_tuple:
                st.session_state["cfg_resolucao"] = label
                break

    # FPS
    if "fps_padrao" in cfg_geral:
        st.session_state["cfg_fps"] = int(cfg_geral["fps_padrao"])

    # Pausa
    if "pausa_final_padrao" in cfg_geral:
        st.session_state["cfg_pausa"] = float(cfg_geral["pausa_final_padrao"])

    # 4. Reconstruir cenas
    novas_cenas = []
    timestamp_base = int(time.time())
    for idx, c in enumerate(cenas_raw, 1):
        uid = f"cena_{idx:02d}_{timestamp_base}"
        tit = c.get("titulo", f"Passo {idx:02d}")
        narr = c.get("texto_narracao", c.get("narracao", ""))
        overlay_val = c.get("overlay_texto")

        # Tarja visual independente
        if "tarja_visual" in c and c["tarja_visual"]:
            tarja_val = str(c["tarja_visual"])
        elif isinstance(overlay_val, str):
            tarja_val = overlay_val
        elif isinstance(overlay_val, dict):
            tarja_val = overlay_val.get("texto", tit)
        else:
            tarja_val = tit

        # Legenda escrita independente
        legenda_val = c.get("legenda") or c.get("texto_legenda") or ""
        if not str(legenda_val).strip() and str(narr).strip():
            legenda_val = str(narr).strip()
        legenda_val = str(legenda_val)

        # Flag de usar legenda na fala
        if "usar_legenda_fala" in c:
            usar_leg_fala = bool(c["usar_legenda_fala"])
        else:
            # Se narração e legenda forem idênticas (ou se narração vazia com legenda preenchida)
            if not str(narr).strip() and str(legenda_val).strip():
                usar_leg_fala = True
                narr = str(legenda_val).strip()
            elif str(narr).strip() and str(legenda_val).strip() and str(narr).strip() == str(legenda_val).strip():
                usar_leg_fala = True
            else:
                usar_leg_fala = False

        tem_overlay = bool(c.get("exibir_overlay", True)) if bool(str(tarja_val).strip()) else bool(overlay_val)

        midia = (
            c.get("video_path")
            or c.get("video")
            or c.get("imagem_path")
            or c.get("imagem")
            or c.get("captura_tela")
            or c.get("midia_path")
            or ""
        )
        pasta_ctx = caminho_origem.parent if (caminho_origem and Path(caminho_origem).is_file()) else None
        achado = resolver_caminho_midia(midia, pasta_ctx)
        if achado and achado.is_file():
            midia = str(achado)

        novas_cenas.append({
            "id": idx,
            "uid": uid,
            "titulo": tit,
            "tarja_visual": tarja_val,
            "narracao": narr,
            "legenda": legenda_val,
            "usar_legenda_fala": usar_leg_fala,
            "caminho_midia": midia,
            "exibir_overlay": tem_overlay,
            "exibir_legenda": bool(c.get("exibir_legenda", True)),
        })
        st.session_state[f"titulo_{uid}"] = tit
        st.session_state[f"tarja_{uid}"] = tarja_val
        st.session_state[f"narracao_{uid}"] = narr
        st.session_state[f"legenda_{uid}"] = legenda_val
        st.session_state[f"usar_legenda_fala_{uid}"] = usar_leg_fala
        st.session_state[f"overlay_{uid}"] = tem_overlay
        st.session_state[f"exibir_legenda_{uid}"] = bool(c.get("exibir_legenda", True))

    st.session_state.scenes = novas_cenas
    st.session_state.scene_counter = len(novas_cenas)
    st.session_state["mensagem_sucesso_projeto"] = f"✅ Projeto '{titulo}' carregado com sucesso ({len(novas_cenas)} cenas)!"


def restaurar_projeto_de_dados(dados: dict, caminho_origem: Optional[Path] = None):
    """
    Agenda a restauração de um projeto para ser aplicada antes da renderização dos widgets,
    evitando StreamlitWidgetAlreadyInstantiatedError.
    """
    cenas_raw = dados.get("cenas") or dados.get("passos") or []
    if not isinstance(cenas_raw, list) or len(cenas_raw) == 0:
        st.error("O arquivo de projeto não contém cenas válidas ('cenas' ou 'passos').")
        return

    st.session_state["_projeto_pendente_carregar"] = (dados, caminho_origem)
    st.rerun()


def executar_novo_projeto():
    """Reinicia a área de trabalho para um projeto em branco antes da renderização dos widgets."""
    limpar_todos_arquivos_temporarios(remover_videos_saida=True)
    st.session_state.video_gerado = None
    st.session_state.video_nome_arquivo = None

    for c in st.session_state.get("scenes", []):
        uid = c.get("uid")
        if uid:
            st.session_state.pop(f"titulo_{uid}", None)
            st.session_state.pop(f"tarja_{uid}", None)
            st.session_state.pop(f"narracao_{uid}", None)
            st.session_state.pop(f"legenda_{uid}", None)
            st.session_state.pop(f"usar_legenda_fala_{uid}", None)
            st.session_state.pop(f"overlay_{uid}", None)
            st.session_state.pop(f"exibir_legenda_{uid}", None)
            st.session_state.pop(f"audio_preview_{uid}", None)

    st.session_state["input_titulo_projeto"] = "Meu Novo Tutorial em Vídeo"
    st.session_state["cfg_voz_label"] = list(OPCOES_VOZES.keys())[0]
    st.session_state["cfg_taxa_fala"] = "+0%"
    st.session_state["cfg_resolucao"] = list(OPCOES_RESOLUCAO.keys())[0]
    st.session_state["cfg_fps"] = 30
    st.session_state["cfg_pausa"] = 0.5

    uid = f"scene_1_{int(time.time())}"
    st.session_state.scenes = [{
        "id": 1,
        "uid": uid,
        "titulo": "Passo 01",
        "tarja_visual": "Passo 01",
        "narracao": "",
        "legenda": "",
        "usar_legenda_fala": True,
        "caminho_midia": "",
        "exibir_overlay": True,
        "exibir_legenda": True,
    }]
    st.session_state[f"titulo_{uid}"] = "Passo 01"
    st.session_state[f"tarja_{uid}"] = "Passo 01"
    st.session_state[f"narracao_{uid}"] = ""
    st.session_state[f"legenda_{uid}"] = ""
    st.session_state[f"usar_legenda_fala_{uid}"] = True
    st.session_state[f"overlay_{uid}"] = True
    st.session_state[f"exibir_legenda_{uid}"] = True
    st.session_state.scene_counter = 1
    st.session_state["mensagem_sucesso_projeto"] = "✨ Novo projeto criado com sucesso!"


def novo_projeto():
    """Agenda a criação de um novo projeto para o início do ciclo."""
    st.session_state["_novo_projeto_pendente"] = True
    st.rerun()





# ==============================================================================
# Gerenciamento de Estado da Sessão (Session State)
# ==============================================================================

if "scene_counter" not in st.session_state:
    st.session_state.scene_counter = 1

if "scenes" not in st.session_state:
    st.session_state.scenes = [
        {"id": 1, "uid": f"scene_1_{int(time.time())}"}
    ]

if "video_gerado" not in st.session_state:
    st.session_state.video_gerado = None

if "video_nome_arquivo" not in st.session_state:
    st.session_state.video_nome_arquivo = "tutorial.mp4"

if "input_titulo_projeto" not in st.session_state:
    st.session_state["input_titulo_projeto"] = "Meu Vídeo Tutorial"

# Execução de ações pendentes antes da instanciação de qualquer widget
if "_projeto_pendente_carregar" in st.session_state:
    dados_pendentes, caminho_origem = st.session_state.pop("_projeto_pendente_carregar")
    executar_restauracao_projeto(dados_pendentes, caminho_origem)

if "_novo_projeto_pendente" in st.session_state:
    st.session_state.pop("_novo_projeto_pendente", None)
    executar_novo_projeto()


def adicionar_cena():
    st.session_state.scene_counter += 1
    nova_uid = f"scene_{st.session_state.scene_counter}_{int(time.time())}"
    nova_cena = {
        "id": st.session_state.scene_counter,
        "uid": nova_uid,
        "usar_legenda_fala": True,
    }
    st.session_state[f"usar_legenda_fala_{nova_uid}"] = True
    st.session_state.scenes.append(nova_cena)


def remover_cena(uid: str):
    if len(st.session_state.scenes) > 1:
        st.session_state.scenes = [s for s in st.session_state.scenes if s["uid"] != uid]
        st.session_state.pop(f"titulo_{uid}", None)
        st.session_state.pop(f"tarja_{uid}", None)
        st.session_state.pop(f"narracao_{uid}", None)
        st.session_state.pop(f"legenda_{uid}", None)
        st.session_state.pop(f"usar_legenda_fala_{uid}", None)
        st.session_state.pop(f"overlay_{uid}", None)
        st.session_state.pop(f"exibir_legenda_{uid}", None)
        st.session_state.pop(f"audio_preview_{uid}", None)
    else:
        st.warning("O tutorial deve ter no mínimo uma cena.")


# ==============================================================================
# Barra Lateral: Configurações Gerais do Projeto
# ==============================================================================

with st.sidebar:
    st.header("⚙️ Configurações Gerais")

    # Nome do Projeto
    titulo_projeto = st.text_input(
        "📌 Nome do Projeto / Vídeo",
        key="input_titulo_projeto",
        help="Título exibido nos logs e utilizado como base no nome do arquivo final.",
    )

    # --------------------------------------------------------------------------
    # Painel de Gerenciamento de Projetos (Salvar / Carregar)
    # --------------------------------------------------------------------------
    with st.expander("📁 Gerenciar Projeto (Exportar & Importar)", expanded=True):
        tab_exportar, tab_importar, tab_novo = st.tabs(["📦 Baixar", "📂 Importar", "✨ Novo"])

        with tab_exportar:
            cenas_atuais = coletar_cenas_atuais()
            cenas_com_midia = sum(
                1 for c in cenas_atuais
                if (c["upload_obj"] is not None) or (c["caminho_disco"] and resolver_caminho_midia(c["caminho_disco"]))
            )
            st.info(f"📊 **{len(cenas_atuais)} Cenas** | 🖼️ **{cenas_com_midia} Mídias Anexadas**")
            st.warning(
                "⚠️ **Aviso**: O servidor não armazena projetos. Se você não baixar o projeto ou não gerar o vídeo, "
                "todo o trabalho será perdido ao fechar ou recarregar a página."
            )

            zip_bytes, nome_zip = gerar_zip_projeto_atual()
            st.download_button(
                label="📦 Baixar Projeto Completo (.ZIP com mídias)",
                data=zip_bytes,
                file_name=nome_zip,
                mime="application/zip",
                use_container_width=True,
                type="primary",
                help="Recomendado: Baixa pacote compactado (.zip) com roteiro e todas as mídias (fotos/vídeos) para salvar no seu computador.",
            )

            json_str, nome_down = gerar_json_projeto_atual()
            st.download_button(
                label="📄 Baixar Apenas Roteiro (.JSON)",
                data=json_str,
                file_name=nome_down,
                mime="application/json",
                use_container_width=True,
                help="Baixa apenas o arquivo JSON do roteiro (sem mídias embutidas).",
            )

        with tab_importar:
            st.caption("Restaure um projeto salvo anteriormente no seu computador.")
            arq_externo_upload = st.file_uploader(
                "Envie o arquivo do projeto (.zip ou .json):",
                type=["zip", "json"],
                key="uploader_projeto_externo",
                help="Envie um pacote compactado .zip (com mídias e roteiro) ou um arquivo .json.",
            )
            if arq_externo_upload is not None:
                ext = Path(arq_externo_upload.name).suffix.lower()
                if ext == ".zip":
                    if st.button("📦 Importar Pacote .ZIP (com mídias)", key="btn_restaurar_upload_zip", use_container_width=True, type="primary"):
                        descompactar_e_restaurar_zip(arq_externo_upload.getvalue(), arq_externo_upload.name)
                else:
                    if st.button("📂 Importar Roteiro .JSON", key="btn_restaurar_upload_json", use_container_width=True, type="primary"):
                        try:
                            dados_p = json.loads(arq_externo_upload.getvalue().decode("utf-8"))
                            restaurar_projeto_de_dados(dados_p)
                        except Exception as e:
                            st.error(f"Erro ao processar JSON: {e}")

            st.markdown("---")
            with st.expander("⭐ Modelos Prontos de Exemplo", expanded=False):
                modelos_disp = listar_modelos_disponiveis()
                if modelos_disp:
                    opcoes_mod = {m["nome_exibicao"]: m for m in modelos_disp}
                    mod_selecionado = st.selectbox(
                        "Selecione um modelo:",
                        options=list(opcoes_mod.keys()),
                        key="select_modelo_carregar",
                    )
                    if st.button("⭐ Carregar Modelo", key="btn_carregar_modelo_sel", use_container_width=True):
                        try:
                            caminho_arq = opcoes_mod[mod_selecionado]["caminho_arquivo"]
                            with open(caminho_arq, "r", encoding="utf-8") as f_m:
                                dados_m = json.load(f_m)
                            restaurar_projeto_de_dados(dados_m, caminho_arq)
                        except Exception as e:
                            st.error(f"Erro ao carregar modelo: {e}")

        with tab_novo:
            st.caption("Limpa todas as cenas e inicia um projeto limpo com 1 cena em branco.")
            if st.button("✨ Iniciar Projeto em Branco", key="btn_novo_proj_sidebar", use_container_width=True):
                novo_projeto()

            st.markdown("---")
            with st.expander("🧹 Limpeza e Manutenção de Disco", expanded=False):
                st.caption("Remove arquivos temporários, caches de mídia e vídeos antigos gerados.")
                if st.button("🗑️ Limpar Todos Arquivos Temporários", key="btn_limpeza_manual_side", use_container_width=True):
                    rem = limpar_todos_arquivos_temporarios(remover_videos_saida=True)
                    st.session_state.video_gerado = None
                    st.session_state.video_nome_arquivo = None
                    st.success(f"🧹 Limpeza realizada com sucesso! ({rem} itens limpos)")
                    st.rerun()

    st.markdown("---")
    st.subheader("🎙️ Configurações de Locução")

    # Seletor de Vozes Neurais (edge-tts)
    if "cfg_voz_label" not in st.session_state or st.session_state["cfg_voz_label"] not in OPCOES_VOZES:
        st.session_state["cfg_voz_label"] = list(OPCOES_VOZES.keys())[0]

    voz_selecionada_label = st.selectbox(
        "Voz do Locutor (edge-tts)",
        options=list(OPCOES_VOZES.keys()),
        key="cfg_voz_label",
        help="Voz neural utilizada para sintetizar a narração de cada cena.",
    )

    if OPCOES_VOZES[voz_selecionada_label] == "custom":
        if "cfg_voz_custom" not in st.session_state:
            st.session_state["cfg_voz_custom"] = "pt-BR-AntonioNeural"
        voz_padrao = st.text_input(
            "Identificador da Voz (ShortName)",
            key="cfg_voz_custom",
            help="Exemplo: pt-BR-AntonioNeural, en-US-JennyNeural, etc.",
        )
    else:
        voz_padrao = OPCOES_VOZES[voz_selecionada_label]

    if "cfg_taxa_fala" not in st.session_state or st.session_state["cfg_taxa_fala"] not in TAXAS_FALA:
        st.session_state["cfg_taxa_fala"] = "+0%"

    taxa_fala = st.select_slider(
        "⚡ Velocidade da Narração",
        options=TAXAS_FALA,
        key="cfg_taxa_fala",
        help="Acelere ou desacelere a locução sem distorcer o tom de voz.",
    )

    # Botão para ouvir prévia da voz selecionada
    if st.button("🔊 Ouvir Demonstração da Voz", key="btn_preview_voz_global", use_container_width=True, help="Ouvir uma frase de exemplo com a voz e velocidade selecionadas"):
        frase_teste = "Olá! Esta é uma demonstração da voz neural que narrará o seu vídeo tutorial."
        pasta_prev = Path("temp_streamlit/previews")
        pasta_prev.mkdir(parents=True, exist_ok=True)
        arq_preview_global = pasta_prev / f"amostra_{sanitizar_nome_arquivo(voz_padrao)}_{sanitizar_nome_arquivo(taxa_fala)}.mp3"
        with st.spinner("Carregando voz..."):
            try:
                executar_assincrono(
                    sintetizar_audio(
                        texto=frase_teste,
                        caminho_saida=arq_preview_global,
                        voz=voz_padrao,
                        taxa=taxa_fala,
                    )
                )
                st.session_state["audio_preview_global"] = str(arq_preview_global)
            except Exception as e:
                st.error(f"Erro ao gerar amostra: {e}")

    if "audio_preview_global" in st.session_state and Path(st.session_state["audio_preview_global"]).is_file():
        st.audio(st.session_state["audio_preview_global"], format="audio/mp3", autoplay=True)

    with st.expander("🛠️ Parâmetros Avançados de Vídeo", expanded=False):
        if "cfg_resolucao" not in st.session_state or st.session_state["cfg_resolucao"] not in OPCOES_RESOLUCAO:
            st.session_state["cfg_resolucao"] = list(OPCOES_RESOLUCAO.keys())[0]

        res_label = st.selectbox(
            "Resolução de Saída",
            options=list(OPCOES_RESOLUCAO.keys()),
            key="cfg_resolucao",
            help="Vídeos em resoluções diferentes serão padronizados automaticamente sem distorção.",
        )
        resolucao_padrao = OPCOES_RESOLUCAO[res_label]

        if "cfg_fps" not in st.session_state:
            st.session_state["cfg_fps"] = 30
        fps_padrao = st.slider("Taxa de Quadros (FPS)", min_value=24, max_value=60, step=6, key="cfg_fps")

        if "cfg_pausa" not in st.session_state:
            st.session_state["cfg_pausa"] = 0.5
        pausa_final_padrao = st.slider(
            "Pausa no fim de cada cena (segundos)",
            min_value=0.0,
            max_value=2.0,
            step=0.1,
            key="cfg_pausa",
            help="Duração do congelamento do último quadro para respirar antes da próxima cena.",
        )

    st.markdown("---")
    st.caption("🤖 Powered by **Streamlit**, **edge-tts** e **MoviePy 2.x**")


# ==============================================================================
# Cabeçalho Principal da Aplicação
# ==============================================================================

st.markdown('<div class="main-title">🎬 Gerador Automático de Tutoriais em Vídeo</div>', unsafe_allow_html=True)
st.markdown(
    '<div class="subtitle">Crie tutoriais profissionais com narração neural de alta fidelidade e sincronização de tela automática.</div>',
    unsafe_allow_html=True,
)

if "mensagem_sucesso_projeto" in st.session_state:
    st.success(st.session_state.pop("mensagem_sucesso_projeto"))
if "mensagem_erro_projeto" in st.session_state:
    st.error(st.session_state.pop("mensagem_erro_projeto"))

# ==============================================================================
# Seção de Gerenciamento Dinâmico de Cenas
# ==============================================================================

col_head_left, col_head_right = st.columns([4, 1])
with col_head_left:
    st.subheader("📑 Cenas do Tutorial")
with col_head_right:
    if st.button("✨ Novo", use_container_width=True, help="Iniciar um novo projeto limpo em branco"):
        novo_projeto()

st.write(
    "Adicione as cenas na ordem desejada. Para cada cena, envie **o vídeo gravado OU a captura de tela (screenshot)** e digite o texto correspondente para a narração."
)
st.info(
    "💡 **Dica de Produtividade**: Você pode baixar seu projeto a qualquer momento no painel **'📁 Gerenciar Projeto'** na barra lateral como **.ZIP (com mídias)** ou **.JSON** para guardar seu trabalho no seu computador."
)

with st.expander("🛠️ Guia de Ferramentas Recomendadas (Captura de Imagens e Gravação de Tela)", expanded=False):
    st.caption("Dicas de ferramentas gratuitas e de código aberto para capturar os prints e clipes de vídeo que irão compor as suas cenas:")
    tab_guia_print, tab_guia_video, tab_guia_mobile, tab_guia_dicas = st.tabs([
        "📸 Captura de Imagens (Prints)",
        "🎥 Gravação de Vídeos de Tela",
        "📱 Tutoriais Mobile (Celular)",
        "💡 Boas Práticas de Gravação",
    ])

    with tab_guia_print:
        st.markdown(
            """
            #### 1. **Flameshot** *(Software Livre / FOSS — Altamente Recomendado)*
            - **Sistemas Operacionais:** 🐧 **Linux** | 🪟 **Windows** | 🍎 **macOS**
            - **Por que usar:** É a ferramenta ideal para tutoriais. Possui:
              - **Numeração sequencial em círculos (1, 2, 3):** Ideal para indicar a ordem em que o usuário deve clicar.
              - **Setas, caixas e marca-texto:** Permite destacar botões e campos facilmente.
              - **Desfoque / Pixelização:** Essencial para esconder senhas, e-mails ou dados confidenciais antes de salvar o print.
            - **Como obter:** Linux (`sudo apt install flameshot` ou Flatpak) | Windows e Mac: [flameshot.org](https://flameshot.org).

            ---

            #### 2. **Ksnip** *(Software Livre / FOSS)*
            - **Sistemas Operacionais:** 🐧 **Linux** | 🪟 **Windows** | 🍎 **macOS**
            - **Por que usar:** Interface moderna com abas para editar vários prints simultaneamente, carimbos numéricos personalizáveis, ferramenta de corte (crop) e suporte a marca d'água.
            - **Como obter:** Disponível no GitHub ([ksnip](https://github.com/ksnip/ksnip)) e Flathub.

            ---

            #### 3. **ShareX** *(Software Livre / FOSS)*
            - **Sistemas Operacionais:** 🪟 **Windows** (Exclusivo Windows)
            - **Por que usar:** Um dos aplicativos de captura mais avançados para Windows. Permite anotações instantâneas, gravação de áreas e atalhos customizados.
            - **Como obter:** [getsharex.com](https://getsharex.com) ou na Microsoft Store.

            ---

            #### 4. **Atalhos Nativos do Próprio Sistema (Sem instalar nada):**
            - 🪟 **Windows:** Pressione `Win + Shift + S` para abrir a Ferramenta de Captura rápida com seleção de área.
            - 🍎 **macOS:** Pressione `Cmd + Shift + 4` para selecionar a área desejada e salvar o print na Área de Transferência/Mesa.
            - 🐧 **Linux (GNOME / KDE):** Pressione a tecla `PrtScn` para abrir o menu interativo de seleção de retângulo.
            """
        )

    with tab_guia_video:
        st.markdown(
            """
            #### 1. **Kooha** *(Software Livre / FOSS — Recomendado para Linux Moderno)*
            - **Sistemas Operacionais:** 🐧 **Linux** (Suporta nativamente **Wayland** e **X11**)
            - **Por que usar:** Interface limpa e minimalista (GTK4). Permite desenhar um retângulo na tela, gravar com áudio/microfone e exportar diretamente em **MP4** ou **WebM** com 60 FPS.
            - **Como obter:** Via Flatpak: `flatpak install flathub io.github.seadve.Kooha`.

            ---

            #### 2. **Peek** *(Software Livre / FOSS)*
            - **Sistemas Operacionais:** 🐧 **Linux** (X11)
            - **Por que usar:** Abre uma janela com moldura transparente que você posiciona sobre a área que deseja gravar. Excelente para pequenos clipes de 3 a 8 segundos em MP4 ou WebM.
            - **Como obter:** `sudo apt install peek`.

            ---

            #### 3. **OBS Studio** *(Software Livre / FOSS — Padrão Profissional)*
            - **Sistemas Operacionais:** 🐧 **Linux** | 🪟 **Windows** | 🍎 **macOS** (Universal)
            - **Por que usar:** Permite travar a tela em resoluções padronizadas como **1920x1080 (16:9)** ou **1080x1920 (9:16 Shorts)**, usar atalhos para iniciar/parar e capturar janelas específicas.
            - **Como obter:** [obsproject.com](https://obsproject.com) ou nos repositórios da sua distribuição.

            ---

            #### 4. **SimpleScreenRecorder (SSR)** *(Software Livre / FOSS)*
            - **Sistemas Operacionais:** 🐧 **Linux** (X11)
            - **Por que usar:** Extremamente leve, não consome processador e grava diretamente em MP4 pré-otimizado (H.264/AAC).
            - **Como obter:** `sudo apt install simplescreenrecorder`.

            ---

            #### 5. **Gravadores Nativos Embutidos no Sistema (Sem instalar nada):**
            - 🪟 **Windows 10/11:** Pressione `Win + Alt + R` (Gravação do Xbox Game Bar) ou use a Ferramenta de Captura do Windows 11 no modo de vídeo.
            - 🍎 **macOS:** Pressione `Cmd + Shift + 5` e selecione a opção "Gravar Parte Selecionada".
            - 🐧 **Linux (GNOME 42+):** Pressione `Ctrl + Alt + Shift + R` ou `PrtScn` e selecione o ícone de filmadora.
            """
        )

    with tab_guia_mobile:
        st.markdown(
            """
            #### 📱 **Scrcpy (Genymobile)** *(Software Livre / FOSS)*
            - **Sistemas Operacionais:** 🐧 **Linux** | 🪟 **Windows** | 🍎 **macOS**
            - **Para gravar:** Dispositivos móveis com sistema operacional **Android**.
            - **Por que usar:**
              - Espelha a tela do seu celular Android no computador via cabo USB ou Wi-Fi com **latência zero** e altíssima resolução.
              - Permite gravar diretamente para um arquivo de vídeo no computador:
                ```bash
                scrcpy --record clipe_celular.mp4
                ```
              - Já gera o vídeo na proporção vertical exata (**9:16**), perfeita para tutoriais voltados para smartphones, Instagram Reels, TikTok e YouTube Shorts.
            - **Como obter:** Linux (`sudo apt install scrcpy adb`) | Windows e Mac: [github.com/Genymobile/scrcpy](https://github.com/Genymobile/scrcpy).
            """
        )

    with tab_guia_dicas:
        st.markdown(
            """
            #### 💡 Dicas de Ouro para Montar Vídeos no `video-automate`:

            1. **Padronize a Proporção da Mídia:**
               - Para vídeos horizontais comuns (**16:9**), procure gravar na proporção de **1920x1080** ou mantenha o navegador maximizado.
               - Para vídeos verticais (**9:16**), utilize o Scrcpy ou redimensione a janela para o formato de smartphone antes de capturar.
            2. **Imagem Estática (.png/.jpg) vs. Vídeo (.mp4/.webm):**
               - Se a tela não possui animações (é apenas uma página com botões ou formulário estático), **prefira tirar uma captura de tela com anotações (setas/números)**. O gerador manterá a imagem exibida durante todo o tempo da narração automaticamente.
               - Use vídeos gravados apenas quando houver movimentos relevantes (ex: arrastar e soltar, transições ou animações).
            3. **Duração Ideal dos Clipes de Vídeo:**
               - Mantenha os clipes dinâmicos entre **3 e 8 segundos**, mostrando estritamente a ação que a voz neural está descrevendo naquele momento.
            4. **Oculte Dados Pessoais com Antecedência:**
               - Use a ferramenta de desfoque (blur) ou tarja preta do Flameshot/Ksnip para esconder senhas, telefones, e-mails ou nomes de clientes antes de anexar a mídia.
            """
        )


dados_cenas_coletados = []

for idx, cena_meta in enumerate(st.session_state.scenes):
    uid = cena_meta["uid"]
    numero_cena = idx + 1

    with st.container(border=True):
        col_header_1, col_header_2 = st.columns([6, 1])
        with col_header_1:
            st.markdown(f"#### 🎞️ Cena {numero_cena:02d}")
        with col_header_2:
            if len(st.session_state.scenes) > 1:
                st.button(
                    "🗑️ Remover",
                    key=f"btn_remove_{uid}",
                    on_click=remover_cena,
                    args=(uid,),
                    help="Remover esta cena",
                )

        col_esq, col_dir = st.columns([1, 1], gap="medium")

        with col_esq:
            val_padrao_titulo = cena_meta.get("titulo", f"Passo {numero_cena:02d}")
            if f"titulo_{uid}" not in st.session_state:
                st.session_state[f"titulo_{uid}"] = val_padrao_titulo

            titulo_cena = st.text_input(
                "Título / Identificador da Cena",
                key=f"titulo_{uid}",
                help="Nome descritivo da cena para organização interna.",
            )

            # Tarja Visual (Lower-Third) separada da Legenda
            val_padrao_tarja = cena_meta.get("tarja_visual") or cena_meta.get("overlay_texto") or val_padrao_titulo
            if f"tarja_{uid}" not in st.session_state:
                st.session_state[f"tarja_{uid}"] = val_padrao_tarja

            tarja_texto = st.text_input(
                "🏷️ Texto da Tarja Visual no Vídeo (Lower-Third)",
                key=f"tarja_{uid}",
                placeholder=f"Ex: Passo {numero_cena:02d}: Título do Destaque",
                help="Texto exibido na tarja elegante estilizada sobre o vídeo (barra translúcida com detalhe azul).",
            )

            if f"overlay_{uid}" not in st.session_state:
                st.session_state[f"overlay_{uid}"] = bool(cena_meta.get("exibir_overlay", True))

            exibir_overlay = st.checkbox(
                "Exibir esta tarja visual estilizada no vídeo",
                key=f"overlay_{uid}",
                help="Gera a tarja elegante translúcida com cantos arredondados contendo o texto da tarja visual.",
            )

            media_file = st.file_uploader(
                "Upload da Mídia: Captura de Tela (.png, .jpg) ou Vídeo (.mp4, .webm)",
                type=["mp4", "webm", "mov", "png", "jpg", "jpeg", "webp"],
                key=f"upload_{uid}",
                help="Envie um vídeo gravado da ação OU uma imagem de captura da tela (screenshot). Imagens ficarão visíveis durante toda a narração.",
            )

            # Recupera o texto da legenda e configurações atuais da cena para prévia e legendagem
            texto_leg_preview = str(st.session_state.get(f"legenda_{uid}", cena_meta.get("legenda", ""))).strip()
            if not texto_leg_preview and cena_meta.get("narracao"):
                texto_leg_preview = str(cena_meta.get("narracao", "")).strip()
            exibir_leg_preview = bool(st.session_state.get(f"exibir_legenda_{uid}", cena_meta.get("exibir_legenda", True)))
            subtitles_vtt = (
                obter_caminho_vtt_legenda(uid, texto_leg_preview)
                if (exibir_leg_preview and texto_leg_preview)
                else None
            )

            caminho_disco = resolver_caminho_midia(cena_meta.get("caminho_midia"))
            caminho_midia_efetivo = None

            if media_file is not None:
                # Salva em cache imediato para que a mídia nunca seja perdida em reruns
                pasta_cache_midias = Path("temp_streamlit/midias_anexadas")
                pasta_cache_midias.mkdir(parents=True, exist_ok=True)
                ext_midia = Path(media_file.name).suffix.lower() or ".mp4"
                nome_limpo = sanitizar_nome_arquivo(Path(media_file.name).stem)
                arq_cache = pasta_cache_midias / f"{uid}_{nome_limpo}{ext_midia}"
                if not arq_cache.is_file() or arq_cache.stat().st_size != media_file.size:
                    with open(arq_cache, "wb") as f_c:
                        f_c.write(media_file.getvalue())
                cena_meta["caminho_midia"] = str(arq_cache)
                caminho_midia_efetivo = str(arq_cache)

                if ext_midia in [".png", ".jpg", ".jpeg", ".webp"]:
                    st.image(
                        media_file,
                        caption=f"📸 Captura de Tela (Upload): {media_file.name}",
                        use_container_width=True,
                    )
                else:
                    st.video(media_file, subtitles=subtitles_vtt)
                    st.caption(f"📹 Vídeo anexado: **{media_file.name}** ({media_file.size / 1024:.1f} KB)")
            elif caminho_disco and caminho_disco.is_file():
                ext_midia = caminho_disco.suffix.lower()
                caminho_midia_efetivo = str(caminho_disco)
                col_m_view, col_m_del = st.columns([4, 1])
                with col_m_view:
                    if ext_midia in [".png", ".jpg", ".jpeg", ".webp"]:
                        st.image(
                            str(caminho_disco),
                            caption=f"📸 Captura Vinculada ao Projeto: {caminho_disco.name}",
                            use_container_width=True,
                        )
                    else:
                        st.video(str(caminho_disco), subtitles=subtitles_vtt)
                        st.caption(f"📹 Vídeo vinculado: **{caminho_disco.name}** ({caminho_disco.stat().st_size / 1024:.1f} KB)")
                with col_m_del:
                    if st.button("🗑️", key=f"btn_remover_midia_{uid}", help="Desvincular esta mídia da cena"):
                        cena_meta["caminho_midia"] = ""
                        st.rerun()
            else:
                st.info("📎 Nenhuma mídia vinculada a esta cena. Envie uma imagem ou vídeo acima.")

            # Prévia visual composta (frame com tarja visual + legenda discreta)
            tarja_prev_txt = str(st.session_state.get(f"tarja_{uid}", cena_meta.get("tarja_visual", titulo_cena))).strip()
            exibir_tarja_prev = bool(st.session_state.get(f"overlay_{uid}", cena_meta.get("exibir_overlay", True)))
            if caminho_midia_efetivo and (texto_leg_preview or tarja_prev_txt):
                with st.expander("👁️ Prévia da Cena com Tarja e Legenda", expanded=False):
                    try:
                        img_prev = gerar_previa_frame_composto(
                            caminho_midia=caminho_midia_efetivo,
                            texto_tarja=tarja_prev_txt,
                            texto_legenda=texto_leg_preview,
                            exibir_tarja=exibir_tarja_prev,
                            exibir_legenda=exibir_leg_preview,
                        )
                        st.image(
                            img_prev,
                            caption="Como esta cena será exibida no vídeo final (Tarja Visual + Legenda Discreta)",
                            use_container_width=True,
                        )
                    except Exception as err_prev:
                        st.caption(f"Prévia indisponível: {err_prev}")

        with col_dir:
            # ==========================================================
            # ÁREA 1: TEXTO DA LEGENDA (ESCRITA FORMAL DA CENA)
            # ==========================================================
            st.markdown("##### 💬 Texto da Legenda *(Escrita Formal / Roteiro)*")
            val_padrao_legenda = cena_meta.get("legenda", "")
            if not val_padrao_legenda and cena_meta.get("narracao"):
                val_padrao_legenda = cena_meta.get("narracao", "")
            if f"legenda_{uid}" not in st.session_state:
                st.session_state[f"legenda_{uid}"] = val_padrao_legenda

            legenda_texto = st.text_area(
                "Texto da Legenda Escrita",
                placeholder="Ex: Acesse o portal capacitacao.uefs.br e clique em Moodle para continuar...",
                height=75,
                key=f"legenda_{uid}",
                help="Texto escrito da legenda com a ortografia formal correta (ex: UEFS, Moodle, 1º Passo).",
            )

            if f"exibir_legenda_{uid}" not in st.session_state:
                st.session_state[f"exibir_legenda_{uid}"] = bool(cena_meta.get("exibir_legenda", True))

            exibir_legenda = st.checkbox(
                "Exibir esta legenda discreta no vídeo",
                key=f"exibir_legenda_{uid}",
                help="Exibe o texto da legenda de forma discreta, elegante e centralizada no rodapé do vídeo.",
            )

            # ==========================================================
            # FLAG DE SINCRONIZAÇÃO: APLICAR LEGENDA NA FALA
            # ==========================================================
            st.markdown("---")
            val_padrao_usar_leg = cena_meta.get("usar_legenda_fala")
            if val_padrao_usar_leg is None:
                narr_existente = cena_meta.get("narracao", "")
                val_padrao_usar_leg = bool(not narr_existente or narr_existente.strip() == val_padrao_legenda.strip())

            if f"usar_legenda_fala_{uid}" not in st.session_state:
                st.session_state[f"usar_legenda_fala_{uid}"] = val_padrao_usar_leg

            usar_legenda_fala = st.checkbox(
                "🪄 Usar texto da legenda diretamente para a fala (Locução Neural)",
                key=f"usar_legenda_fala_{uid}",
                help="Quando ativado, a voz neural falará exatamente o texto da legenda. Desmarque para personalizar a fala foneticamente (ex: trocar 'Moodle' por 'Muudol' ou 'UEFS' por 'Uéfis').",
            )

            # ==========================================================
            # ÁREA 2: FALA DA CENA (LOCUÇÃO NEURAL / AJUSTE FONÉTICO)
            # ==========================================================
            st.markdown("##### 🗣️ Fala da Cena *(Locução Neural / Ajuste Fonético)*")

            val_padrao_narracao = cena_meta.get("narracao", "")
            if f"narracao_{uid}" not in st.session_state:
                st.session_state[f"narracao_{uid}"] = val_padrao_narracao

            if usar_legenda_fala:
                # Sincronização automática com a legenda
                st.session_state[f"narracao_{uid}"] = legenda_texto
                st.caption("🔒 **Fala sincronizada com a legenda:** A voz neural lerá o texto escrito acima. Para ajustar palavras foneticamente (ex: siglas ou termos em inglês), desmarque a opção acima.")
                narracao_texto = st.text_area(
                    "Texto que será Falado (Locução Neural)",
                    key=f"narracao_{uid}",
                    height=75,
                    disabled=True,
                    help="Texto lido pela voz neural sintetizada para esta cena.",
                )
                texto_efetivo_fala = legenda_texto.strip()
            else:
                # Modo independente: permite personalização e ajuste fonético
                if not st.session_state.get(f"narracao_{uid}") and legenda_texto.strip():
                    st.session_state[f"narracao_{uid}"] = legenda_texto.strip()

                col_btn_copy, col_txt_info = st.columns([2, 3])
                with col_btn_copy:
                    if st.button("📋 Copiar da Legenda", key=f"btn_copiar_leg_{uid}", help="Copiar o texto atual da legenda para a fala como ponto de partida"):
                        st.session_state[f"narracao_{uid}"] = legenda_texto
                        st.rerun()
                with col_txt_info:
                    st.caption("✍️ *Ajuste fonético ativado (edição independente)*")

                narracao_texto = st.text_area(
                    "Texto que será Falado (Locução Neural)",
                    placeholder="Digite como a voz neural deve pronunciar (ex: Acesse o portal da Uéfis e clique em Muudol...)",
                    height=75,
                    key=f"narracao_{uid}",
                    help="Texto lido pela voz neural sintetizada. Ajuste foneticamente palavras em inglês, siglas ou números para a pronúncia correta.",
                )
                texto_efetivo_fala = narracao_texto.strip() if narracao_texto else ""

            # Contagem de caracteres e estimativa rápida
            caracteres = len(texto_efetivo_fala)
            palavras = len(texto_efetivo_fala.split()) if texto_efetivo_fala else 0
            tempo_estimado = round(palavras / 2.5) if palavras > 0 else 0
            st.caption(f"📝 {caracteres} caracteres | {palavras} palavras (~{tempo_estimado}s de áudio estimado)")

            # Botão para ouvir a prévia do áudio desta cena
            if st.button("🔊 Ouvir Narração Desta Cena", key=f"btn_audio_{uid}", use_container_width=True, help="Ouvir como a voz neural pronunciará o texto desta cena antes de gerar o vídeo"):
                if texto_efetivo_fala:
                    pasta_prev = Path("temp_streamlit/previews")
                    pasta_prev.mkdir(parents=True, exist_ok=True)
                    preview_cena_path = pasta_prev / f"preview_cena_{uid}.mp3"
                    with st.spinner("Gerando áudio da cena..."):
                        try:
                            executar_assincrono(
                                sintetizar_audio(
                                    texto=texto_efetivo_fala,
                                    caminho_saida=preview_cena_path,
                                    voz=voz_padrao,
                                    taxa=taxa_fala,
                                )
                            )
                            st.session_state[f"audio_preview_{uid}"] = str(preview_cena_path)
                        except Exception as e:
                            st.error(f"Erro ao gerar áudio: {e}")
                else:
                    st.warning("Digite o texto da legenda ou fala para poder ouvir a prévia.")

            if f"audio_preview_{uid}" in st.session_state and Path(st.session_state[f"audio_preview_{uid}"]).is_file():
                st.audio(st.session_state[f"audio_preview_{uid}"], format="audio/mp3", autoplay=True)

        caminho_disco_str = str(caminho_disco) if (caminho_disco and caminho_disco.is_file()) else None
        texto_tarja_efetivo = tarja_texto.strip() if tarja_texto else ""
        dados_cenas_coletados.append({
            "numero": numero_cena,
            "id": f"cena_{numero_cena:02d}",
            "titulo": titulo_cena.strip() or f"Cena {numero_cena}",
            "tarja_visual": texto_tarja_efetivo,
            "arquivo_video": media_file,
            "caminho_midia_disco": caminho_disco_str,
            "narracao": texto_efetivo_fala,
            "legenda": legenda_texto.strip() if legenda_texto else "",
            "usar_legenda_fala": bool(usar_legenda_fala),
            "exibir_overlay": exibir_overlay and bool(texto_tarja_efetivo),
            "exibir_legenda": bool(exibir_legenda) and bool(legenda_texto.strip() if legenda_texto else False),
        })



# Botão para adicionar mais cenas
col_add, _ = st.columns([2, 5])
with col_add:
    st.button("➕ Adicionar Nova Cena", on_click=adicionar_cena, use_container_width=True)

st.markdown("---")

# ==============================================================================
# Pipeline de Processamento e Execução
# ==============================================================================

col_exec, col_info = st.columns([2, 3])

with col_exec:
    botao_gerar = st.button(
        "🚀 Gerar Vídeo Tutorial",
        type="primary",
        use_container_width=True,
    )

with col_info:
    st.caption(
        f"Total de cenas configuradas: **{len(dados_cenas_coletados)}** | Voz ativa: **{voz_padrao}**"
    )

if botao_gerar:
    # 1. Validações pré-execução
    erros = []
    for c in dados_cenas_coletados:
        tem_midia = (c["arquivo_video"] is not None) or (
            c.get("caminho_midia_disco") and Path(c["caminho_midia_disco"]).is_file()
        )
        if not tem_midia:
            erros.append(f"Cena {c['numero']:02d}: Você precisa anexar uma captura de tela (imagem) ou um vídeo.")
        if not c["narracao"] and not c["legenda"]:
            erros.append(f"Cena {c['numero']:02d}: Digite o texto da legenda ou da narração para a cena.")

    if erros:
        for err in erros:
            st.error(f"⚠️ {err}")
        st.stop()

    # Limpa resíduos anteriores de áudios e vídeos antes de iniciar
    limpar_todos_arquivos_temporarios(remover_videos_saida=True)

    # 2. Preparação de diretórios temporários e destino
    timestamp = int(time.time())
    pasta_trabalho = Path("temp_streamlit") / f"job_{timestamp}"
    pasta_uploads = pasta_trabalho / "uploads"
    pasta_audios = pasta_trabalho / "audios"
    pasta_saida = Path("saida")

    pasta_uploads.mkdir(parents=True, exist_ok=True)
    pasta_audios.mkdir(parents=True, exist_ok=True)
    pasta_saida.mkdir(parents=True, exist_ok=True)

    nome_seguro = sanitizar_nome_arquivo(titulo_projeto)
    caminho_video_final = pasta_saida / f"{nome_seguro}_{timestamp}.mp4"

    # Componentes de progresso no Streamlit
    progress_bar = st.progress(0)
    status_box = st.status("Iniciando geração do vídeo tutorial...", expanded=True)

    clipes_para_fechar = []

    try:
        total_cenas = len(dados_cenas_coletados)

        # Salvar arquivos enviados no disco local
        status_box.write("📥 Gravando mídias (vídeos e capturas de tela) no ambiente de processamento...")
        cenas_prontas: List[Tuple[Cena, Path]] = []

        for c in dados_cenas_coletados:
            if c["arquivo_video"] is not None:
                ext = Path(c["arquivo_video"].name).suffix or ".mp4"
                video_temp_path = pasta_uploads / f"{c['id']}{ext}"
                with open(video_temp_path, "wb") as f_out:
                    f_out.write(c["arquivo_video"].getbuffer())
            elif c.get("caminho_midia_disco") and Path(c["caminho_midia_disco"]).is_file():
                orig = Path(c["caminho_midia_disco"])
                ext = orig.suffix or ".png"
                video_temp_path = pasta_uploads / f"{c['id']}{ext}"
                shutil.copyfile(orig, video_temp_path)
            else:
                achado = resolver_caminho_midia(c.get("caminho_midia_disco"))
                if achado and achado.is_file():
                    ext = achado.suffix or ".png"
                    video_temp_path = pasta_uploads / f"{c['id']}{ext}"
                    shutil.copyfile(achado, video_temp_path)
                else:
                    raise FileNotFoundError(f"Arquivo de mídia da Cena {c['numero']:02d} não encontrado.")

            texto_tarja = c.get("tarja_visual", "").strip() or c["titulo"]
            overlay_cfg = (
                OverlayTextoConfig(texto=texto_tarja, posicao="inferior_esquerdo")
                if (c["exibir_overlay"] and texto_tarja)
                else None
            )

            # Fala da cena: usa o texto de narração (ou fallback para a legenda)
            texto_fala = c["narracao"] if c["narracao"] else c.get("legenda", "")
            texto_legenda_final = c.get("legenda", "").strip() or texto_fala
            exibir_legenda_final = bool(c.get("exibir_legenda", True)) and bool(texto_legenda_final)

            obj_cena = Cena(
                id=c["id"],
                titulo=c["titulo"],
                video_path=video_temp_path,
                texto_narracao=texto_fala,
                voz=voz_padrao,
                taxa_fala=taxa_fala,
                overlay_texto=overlay_cfg,
                imagem_destaque=None,
                pausa_final=pausa_final_padrao,
                legenda=texto_legenda_final,
                tarja_visual=texto_tarja,
                exibir_legenda=exibir_legenda_final,
            )
            cenas_prontas.append((obj_cena, video_temp_path))

        config_geral = ConfiguracaoGeral(
            voz_padrao=voz_padrao,
            taxa_fala_padrao=taxa_fala,
            volume_padrao="+0%",
            resolucao_padrao=resolucao_padrao,
            fps_padrao=fps_padrao,
            pausa_final_padrao=pausa_final_padrao,
            video_saida=caminho_video_final,
            manter_audios_temp=False,
        )

        # ----------------------------------------------------------------------
        # ETAPA 1: Síntese de Voz com edge-tts (0% a 40%)
        # ----------------------------------------------------------------------
        status_box.write("🎙️ **[Etapa 1/3]** Gerando narração neural com edge-tts...")
        arquivos_audio: List[Path] = []

        for i, (cena_obj, _) in enumerate(cenas_prontas, 1):
            caminho_audio = pasta_audios / f"{cena_obj.id}.mp3"
            arquivos_audio.append(caminho_audio)

            status_box.write(f"   🔊 Sintetizando Cena {i}/{total_cenas}: *'{cena_obj.titulo}'*...")
            executar_assincrono(
                sintetizar_audio(
                    texto=cena_obj.texto_narracao,
                    caminho_saida=caminho_audio,
                    voz=cena_obj.voz or voz_padrao,
                    taxa=cena_obj.taxa_fala or taxa_fala,
                    volume=config_geral.volume_padrao,
                )
            )
            # Atualiza barra proporcionalmente
            progresso_atual = int((i / total_cenas) * 35)
            progress_bar.progress(progresso_atual)

        # ----------------------------------------------------------------------
        # ETAPA 2: Edição e Sincronização com MoviePy (40% a 80%)
        # ----------------------------------------------------------------------
        status_box.write("🎞️ **[Etapa 2/3]** Sincronizando mídias, áudio e legendas com MoviePy...")
        clipes_processados = []

        for i, ((cena_obj, _), arq_audio) in enumerate(zip(cenas_prontas, arquivos_audio), 1):
            ext_midia = cena_obj.video_path.suffix.lower()
            tipo_midia_desc = "captura de tela" if ext_midia in [".png", ".jpg", ".jpeg", ".webp"] else "vídeo"
            status_box.write(
                f"   ⚙️ Processando Cena {i}/{total_cenas}: sincronizando {tipo_midia_desc} ({resolucao_padrao[0]}x{resolucao_padrao[1]})..."
            )
            clipe = processar_cena_individual(
                cena=cena_obj,
                caminho_audio=arq_audio,
                config_geral=config_geral,
            )
            clipes_processados.append(clipe)
            clipes_para_fechar.append(clipe)

            progresso_atual = 35 + int((i / total_cenas) * 40)
            progress_bar.progress(progresso_atual)

        # ----------------------------------------------------------------------
        # ETAPA 3: Concatenação e Renderização Final (80% a 100%)
        # ----------------------------------------------------------------------
        status_box.write("🎬 **[Etapa 3/3]** Concatenando cenas e renderizando vídeo final em MP4...")
        progress_bar.progress(80)

        video_completo = concatenate_videoclips(clipes_processados, method="compose")
        clipes_para_fechar.append(video_completo)

        duracao_total = video_completo.duration
        status_box.write(
            f"   ⏱️ Duração total calculada: {int(duracao_total // 60)}m {int(duracao_total % 60)}s ({duracao_total:.1f}s)"
        )
        status_box.write("   🎥 Renderizando com codec H.264 + AAC...")

        video_completo.write_videofile(
            str(caminho_video_final),
            fps=fps_padrao,
            codec="libx264",
            audio_codec="aac",
            preset="medium",
            threads=8,
            logger=None,  # Evita poluir logs
        )

        progress_bar.progress(100)
        status_box.update(
            label="🎉 Vídeo gerado com sucesso!",
            state="complete",
            expanded=False,
        )

        st.session_state.video_gerado = str(caminho_video_final)
        st.session_state.video_nome_arquivo = f"{nome_seguro}.mp4"

        st.success(f"Vídeo compilado com sucesso! Veja a prévia e faça o download abaixo.")

    except Exception as e:
        status_box.update(label="❌ Erro durante o processamento do vídeo", state="error", expanded=True)
        st.error(f"Ocorreu um erro durante a geração do vídeo: {str(e)}")
    finally:
        # Fecha e libera recursos do MoviePy
        for clp in clipes_para_fechar:
            try:
                clp.close()
            except Exception:
                pass

        # Limpa arquivos intermediários
        try:
            shutil.rmtree(pasta_trabalho, ignore_errors=True)
        except Exception:
            pass


# ==============================================================================
# Área de Resultado: Player e Download
# ==============================================================================

if st.session_state.video_gerado and Path(st.session_state.video_gerado).is_file():
    st.markdown("---")
    st.subheader("📺 Pré-visualização e Download")

    caminho_resultado = Path(st.session_state.video_gerado)
    tamanho_mb = caminho_resultado.stat().st_size / (1024 * 1024)

    col_preview, col_detalhes = st.columns([3, 2], gap="large")

    with col_preview:
        st.video(str(caminho_resultado))

    with col_detalhes:
        st.markdown("### 📦 Detalhes do Vídeo Gerado")
        st.markdown(f"- **Arquivo**: `{st.session_state.video_nome_arquivo}`")
        st.markdown(f"- **Tamanho**: `{tamanho_mb:.2f} MB`")

        # Lê os bytes na memória para que o download seja garantido mesmo após remoção do disco
        with open(caminho_resultado, "rb") as video_file_bytes:
            conteudo_bytes = video_file_bytes.read()

        st.download_button(
            label="📥 Baixar Vídeo Final (.mp4)",
            data=conteudo_bytes,
            file_name=st.session_state.video_nome_arquivo,
            mime="video/mp4",
            type="primary",
            use_container_width=True,
            help="Clique para baixar o vídeo gerado diretamente para o seu computador",
        )

        st.markdown("---")
        st.markdown("#### 🧹 Conclusão e Limpeza de Disco")
        st.caption(
            "Após baixar o vídeo, finalize o projeto. O arquivo de vídeo compilado e todas as pastas "
            "temporárias serão excluídos do disco, mantendo a pasta do projeto completamente limpa."
        )

        col_fin, col_novo = st.columns(2)
        with col_fin:
            if st.button("🧹 Finalizar e Limpar Disco", type="secondary", use_container_width=True, help="Exclui o vídeo gerado e limpa todas as pastas temporárias"):
                rem = limpar_todos_arquivos_temporarios(remover_videos_saida=True)
                st.session_state.video_gerado = None
                st.session_state.video_nome_arquivo = None
                st.session_state["mensagem_sucesso_projeto"] = f"🎉 Projeto finalizado com sucesso! Todos os arquivos temporários e o vídeo foram removidos ({rem} itens limpos). A pasta está 100% limpa."
                st.rerun()

        with col_novo:
            if st.button("🔄 Novo Projeto", use_container_width=True, help="Inicia um novo projeto em branco limpando arquivos residuais"):
                limpar_todos_arquivos_temporarios(remover_videos_saida=True)
                st.session_state.video_gerado = None
                st.session_state.video_nome_arquivo = None
                novo_projeto()
