#!/usr/bin/env python3
"""
desktop_app.py
==============
Aplicação Desktop Moderna e Nativa em PySide6 (Qt 6) para o
Gerador Automático de Tutoriais em Vídeo com IA.

Suporta compilação nativa para Linux e Windows com PyInstaller.
"""

import os
import sys
import time
import shutil
import platform
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from PIL import Image

from PySide6.QtCore import (
    Qt,
    QThread,
    Signal,
    QSize,
    QUrl,
)
from PySide6.QtGui import (
    QIcon,
    QFont,
    QPixmap,
    QImage,
    QColor,
    QKeySequence,
)
from PySide6.QtMultimedia import (
    QMediaPlayer,
    QAudioOutput,
)
from PySide6.QtWidgets import (
    QApplication,
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QGridLayout,
    QLabel,
    QLineEdit,
    QTextEdit,
    QPushButton,
    QComboBox,
    QSpinBox,
    QDoubleSpinBox,
    QCheckBox,
    QScrollArea,
    QFrame,
    QFileDialog,
    QMessageBox,
    QProgressBar,
    QSplitter,
    QDialog,
    QSizePolicy,
    QStyledItemDelegate,
)

# Imports do motor central e utilitários
import gerador_generico
from gerador_generico import (
    Cena,
    ConfiguracaoGeral,
    OverlayTextoConfig,
    processar_cena_individual,
    sintetizar_audio,
)
from moviepy import concatenate_videoclips

from desktop_utils import (
    OPCOES_VOZES,
    OPCOES_RESOLUCAO,
    TAXAS_FALA,
    sanitizar_nome_arquivo,
    gerar_previa_frame_composto,
    salvar_projeto_json,
    exportar_projeto_zip,
    carregar_projeto_json,
    descompactar_e_importar_zip,
    limpar_arquivos_temporarios,
    sintetizar_audio_sincrono,
    gerar_miniatura_midia,
)

# ==============================================================================
# Tema e Estilos QSS (Modern Dark Theme com Alto Contraste)
# ==============================================================================

ESTILO_QSS = """
QMainWindow, QWidget#CentralWidget {
    background-color: #0b0f19;
    color: #f1f5f9;
    font-family: 'Segoe UI', 'DejaVu Sans', 'Liberation Sans', sans-serif;
    font-size: 13px;
}

QScrollArea {
    border: none;
    background-color: transparent;
}

QScrollBar:vertical {
    border: none;
    background: #111827;
    width: 10px;
    margin: 0px;
    border-radius: 5px;
}

QScrollBar::handle:vertical {
    background: #374151;
    min-height: 20px;
    border-radius: 5px;
}

QScrollBar::handle:vertical:hover {
    background: #4b5563;
}

QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0px;
}

QFrame.card-frame {
    background-color: #151d30;
    border: 1px solid #23304b;
    border-radius: 12px;
    padding: 12px;
}

QFrame.card-frame:hover {
    border-color: #3b82f6;
}

QFrame.sidebar-frame {
    background-color: #111827;
    border-right: 1px solid #1f2937;
    padding: 10px;
}

QLabel {
    color: #cbd5e1;
}

QLabel.title-label {
    font-size: 18px;
    font-weight: 700;
    color: #60a5fa;
}

QLabel.section-label {
    font-size: 14px;
    font-weight: 600;
    color: #93c5fd;
    margin-top: 6px;
    margin-bottom: 2px;
}

QLabel.badge-label {
    background-color: #2563eb;
    color: #ffffff;
    font-size: 11px;
    font-weight: bold;
    padding: 3px 8px;
    border-radius: 6px;
}

QLineEdit, QTextEdit, QSpinBox, QDoubleSpinBox {
    background-color: #1e293b;
    color: #f8fafc;
    border: 1px solid #334155;
    border-radius: 7px;
    padding: 6px 10px;
    selection-background-color: #3b82f6;
}

QLineEdit:focus, QTextEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus {
    border: 1px solid #3b82f6;
    background-color: #1e2a42;
}

/* Estilos de Alto Contraste para QComboBox e seu Dropdown */
QComboBox {
    background-color: #1e293b;
    color: #f8fafc;
    border: 1px solid #334155;
    border-radius: 7px;
    padding: 6px 12px;
    font-weight: 500;
    selection-background-color: #2563eb;
    selection-color: #ffffff;
}

QComboBox:hover {
    border-color: #3b82f6;
    background-color: #243048;
}

QComboBox:focus {
    border: 1px solid #3b82f6;
}

QComboBox::drop-down {
    subcontrol-origin: padding;
    subcontrol-position: top right;
    width: 28px;
    border-left: 1px solid #334155;
    background-color: #1a2333;
    border-top-right-radius: 6px;
    border-bottom-right-radius: 6px;
}

QComboBox::down-arrow {
    image: none;
    border-left: 5px solid transparent;
    border-right: 5px solid transparent;
    border-top: 6px solid #94a3b8;
    margin-right: 4px;
}

QComboBox::down-arrow:hover {
    border-top-color: #60a5fa;
}

/* Menu Dropdown Suspenso (Lista de Opções com Fundo Escuro e Letra Clara) */
QComboBox QAbstractItemView {
    background-color: #0f172a;
    color: #f8fafc;
    border: 1px solid #3b82f6;
    border-radius: 8px;
    padding: 4px;
    selection-background-color: #2563eb;
    selection-color: #ffffff;
    outline: none;
}

QComboBox QAbstractItemView::item {
    background-color: #0f172a;
    color: #f8fafc;
    min-height: 30px;
    padding: 6px 12px;
    border-radius: 5px;
}

QComboBox QAbstractItemView::item:hover {
    background-color: #1d4ed8;
    color: #ffffff;
}

QComboBox QAbstractItemView::item:selected {
    background-color: #2563eb;
    color: #ffffff;
}


QPushButton {
    background-color: #1e293b;
    color: #e2e8f0;
    border: 1px solid #334155;
    border-radius: 8px;
    padding: 7px 14px;
    font-weight: 600;
}

QPushButton:hover {
    background-color: #27354f;
    border-color: #60a5fa;
    color: #ffffff;
}

QPushButton:pressed {
    background-color: #1a2538;
}

QPushButton.primary-btn {
    background-color: #2563eb;
    color: #ffffff;
    border: 1px solid #3b82f6;
    font-size: 14px;
    padding: 10px 20px;
}

QPushButton.primary-btn:hover {
    background-color: #1d4ed8;
    border-color: #60a5fa;
}

QPushButton.danger-btn {
    background-color: #7f1d1d;
    color: #fecaca;
    border: 1px solid #991b1b;
}

QPushButton.danger-btn:hover {
    background-color: #991b1b;
    color: #ffffff;
}

QPushButton.success-btn {
    background-color: #065f46;
    color: #d1fae5;
    border: 1px solid #059669;
}

QPushButton.success-btn:hover {
    background-color: #059669;
    color: #ffffff;
}

QCheckBox {
    color: #cbd5e1;
    spacing: 8px;
}

QCheckBox::indicator {
    width: 18px;
    height: 18px;
    border-radius: 4px;
    border: 1px solid #475569;
    background-color: #1e293b;
}

QCheckBox::indicator:checked {
    background-color: #2563eb;
    border-color: #3b82f6;
}

QProgressBar {
    border: 1px solid #334155;
    border-radius: 8px;
    text-align: center;
    color: #ffffff;
    font-weight: bold;
    background-color: #1e293b;
    height: 22px;
}

QProgressBar::chunk {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #2563eb, stop:1 #8b5cf6);
    border-radius: 7px;
}

QTextEdit.log-console {
    background-color: #090d16;
    color: #a7f3d0;
    font-family: 'Consolas', 'Courier New', monospace;
    font-size: 12px;
    border: 1px solid #1e293b;
    border-radius: 8px;
    line-height: 1.4;
}
"""


# ==============================================================================
# Diálogo de Prévia de Snapshot do Frame
# ==============================================================================

class FramePreviewDialog(QDialog):
    """Exibe o frame composto em alta resolução gerado por PIL/MoviePy."""

    def __init__(self, imagem_pil: Image.Image, titulo_cena: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"Prévia do Frame - {titulo_cena}")
        self.resize(960, 580)
        self.setStyleSheet(ESTILO_QSS)

        layout = QVBoxLayout(self)

        # Informação do preview
        info_label = QLabel(
            f"📸 Snapshot da cena em alta definição ({imagem_pil.width}x{imagem_pil.height}):"
        )
        info_label.setStyleSheet("font-weight: bold; color: #93c5fd; margin-bottom: 4px;")
        layout.addWidget(info_label)

        # Converte PIL Image para QPixmap
        img_bytes = imagem_pil.convert("RGBA").tobytes("raw", "RGBA")
        qim = QImage(img_bytes, imagem_pil.width, imagem_pil.height, QImage.Format_RGBA8888)
        pixmap = QPixmap.fromImage(qim)

        # Label com a imagem redimensionada proporcionalmente
        self.img_label = QLabel()
        self.img_label.setAlignment(Qt.AlignCenter)
        self.img_label.setPixmap(pixmap.scaled(920, 500, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        self.img_label.setStyleSheet("background-color: #090d16; border: 1px solid #334155; border-radius: 8px;")
        layout.addWidget(self.img_label)

        # Botão fechar
        btn_fechar = QPushButton("Fechar Prévia")
        btn_fechar.clicked.connect(self.accept)
        layout.addWidget(btn_fechar, alignment=Qt.AlignRight)


# ==============================================================================
# Diálogo de Visualização de Mídia em Alta Resolução
# ==============================================================================

class MediaViewerDialog(QDialog):
    """Exibe a imagem ou o quadro do vídeo selecionado em tamanho original com rolagem."""

    def __init__(self, caminho_midia: str, titulo_cena: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"Visualizador de Mídia - {Path(caminho_midia).name}")
        self.resize(1050, 680)
        self.setStyleSheet(ESTILO_QSS)

        layout = QVBoxLayout(self)

        p = Path(caminho_midia)
        ext = p.suffix.lower()

        info_label = QLabel(f"📁 <b>{p.name}</b> &nbsp;|&nbsp; Cena: <i>{titulo_cena}</i>")
        info_label.setStyleSheet("color: #93c5fd; font-size: 13px; margin-bottom: 6px;")
        layout.addWidget(info_label)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        lbl_img = QLabel()
        lbl_img.setAlignment(Qt.AlignCenter)
        lbl_img.setStyleSheet("background-color: #090d16; border-radius: 8px;")

        try:
            if ext in [".png", ".jpg", ".jpeg", ".webp", ".bmp"]:
                pixmap = QPixmap(str(p))
            else:
                clip = VideoFileClip(str(p))
                t = min(1.0, max(0.0, clip.duration / 2.0)) if clip.duration else 0.0
                frame_arr = clip.get_frame(t)
                clip.close()
                img = Image.fromarray(frame_arr).convert("RGBA")
                qim = QImage(img.tobytes("raw", "RGBA"), img.width, img.height, QImage.Format_RGBA8888)
                pixmap = QPixmap.fromImage(qim)

            lbl_img.setPixmap(pixmap.scaled(1000, 580, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        except Exception as e:
            lbl_img.setText(f"Não foi possível carregar visualização completa:\n{e}")

        scroll.setWidget(lbl_img)
        layout.addWidget(scroll, stretch=1)

        btn_fechar = QPushButton("Fechar Visualização")
        btn_fechar.clicked.connect(self.accept)
        layout.addWidget(btn_fechar, alignment=Qt.AlignRight)


# ==============================================================================
# Card Interativo de Cena (SceneCardWidget)
# ==============================================================================

class SceneCardWidget(QFrame):
    """Widget de cena interativo contendo seleção de mídia, narração, tarja e preview."""

    solicitar_reordenar = Signal(str, str)  # (uid, 'cima' ou 'baixo')
    solicitar_excluir = Signal(str)         # (uid)
    solicitar_duplicar = Signal(str)        # (uid)

    def __init__(self, uid: str, numero: int, parent=None):
        super().__init__(parent)
        self.uid = uid
        self.numero = numero
        self.setProperty("class", "card-frame")
        self.setObjectName("SceneCard")

        # Player de áudio interno nativo (QMediaPlayer + QAudioOutput)
        self.player = QMediaPlayer(self)
        self.audio_output = QAudioOutput(self)
        self.player.setAudioOutput(self.audio_output)
        self.audio_output.setVolume(1.0)
        self.player.playbackStateChanged.connect(self._ao_mudar_estado_player)

        self._iniciar_ui()

    def _iniciar_ui(self):
        self.layout_principal = QVBoxLayout(self)
        self.layout_principal.setSpacing(10)

        # --- Cabeçalho do Card ---
        header_layout = QHBoxLayout()

        self.badge_num = QLabel(f"Cena {self.numero:02d}")
        self.badge_num.setProperty("class", "badge-label")
        self.badge_num.setStyleSheet(
            "background-color: #2563eb; color: #ffffff; font-weight: bold; border-radius: 6px; padding: 4px 8px;"
        )
        header_layout.addWidget(self.badge_num)

        self.input_titulo = QLineEdit(f"Passo {self.numero:02d}")
        self.input_titulo.setPlaceholderText("Título da cena (ex: Passo 1: Autenticação)...")
        header_layout.addWidget(self.input_titulo, stretch=1)

        # Botões de ação do card
        self.btn_up = QPushButton("▲")
        self.btn_up.setToolTip("Mover cena para cima")
        self.btn_up.setFixedWidth(32)
        self.btn_up.clicked.connect(lambda: self.solicitar_reordenar.emit(self.uid, "cima"))
        header_layout.addWidget(self.btn_up)

        self.btn_down = QPushButton("▼")
        self.btn_down.setToolTip("Mover cena para baixo")
        self.btn_down.setFixedWidth(32)
        self.btn_down.clicked.connect(lambda: self.solicitar_reordenar.emit(self.uid, "baixo"))
        header_layout.addWidget(self.btn_down)

        self.btn_duplicar = QPushButton("📑")
        self.btn_duplicar.setToolTip("Duplicar esta cena")
        self.btn_duplicar.setFixedWidth(32)
        self.btn_duplicar.clicked.connect(lambda: self.solicitar_duplicar.emit(self.uid))
        header_layout.addWidget(self.btn_duplicar)

        self.btn_excluir = QPushButton("🗑️")
        self.btn_excluir.setProperty("class", "danger-btn")
        self.btn_excluir.setToolTip("Excluir esta cena")
        self.btn_excluir.setFixedWidth(32)
        self.btn_excluir.clicked.connect(lambda: self.solicitar_excluir.emit(self.uid))
        header_layout.addWidget(self.btn_excluir)

        self.layout_principal.addLayout(header_layout)

        # --- Seção 1: Seleção de Mídia (Vídeo ou Imagem) ---
        midia_layout = QHBoxLayout()
        label_midia = QLabel("Mídia (Gravação ou Captura):")
        label_midia.setFixedWidth(190)
        midia_layout.addWidget(label_midia)

        self.input_caminho_midia = QLineEdit()
        self.input_caminho_midia.setPlaceholderText("Selecione um vídeo (.mp4, .webm) ou print (.png, .jpg)...")
        midia_layout.addWidget(self.input_caminho_midia, stretch=1)

        self.btn_procurar_midia = QPushButton("📁 Procurar...")
        self.btn_procurar_midia.clicked.connect(self._abrir_seletor_midia)
        midia_layout.addWidget(self.btn_procurar_midia)

        self.layout_principal.addLayout(midia_layout)

        # --- Painel de Miniatura e Conferência Visual da Mídia ---
        self.frame_preview_midia = QFrame()
        self.frame_preview_midia.setStyleSheet(
            "background-color: #0e1628; border: 1px solid #1e293b; border-radius: 8px;"
        )
        layout_preview_midia = QHBoxLayout(self.frame_preview_midia)
        layout_preview_midia.setContentsMargins(10, 8, 10, 8)
        layout_preview_midia.setSpacing(14)

        # Miniatura da Mídia (com tamanho proporcional 16:9)
        self.lbl_thumb_midia = QLabel()
        self.lbl_thumb_midia.setFixedSize(190, 108)
        self.lbl_thumb_midia.setAlignment(Qt.AlignCenter)
        self.lbl_thumb_midia.setStyleSheet(
            "background-color: #111827; border: 1px dashed #374151; border-radius: 6px; color: #64748b;"
        )
        self.lbl_thumb_midia.setText("📷 Sem Mídia")
        layout_preview_midia.addWidget(self.lbl_thumb_midia)

        # Metadados e Ações da Mídia
        col_meta = QVBoxLayout()
        col_meta.setSpacing(4)

        self.lbl_midia_nome = QLabel("Nenhuma mídia selecionada")
        self.lbl_midia_nome.setStyleSheet("font-weight: bold; font-size: 13px; color: #60a5fa;")
        col_meta.addWidget(self.lbl_midia_nome)

        self.lbl_midia_tipo_res = QLabel("Clique em '📁 Procurar...' para carregar um vídeo ou captura de tela.")
        self.lbl_midia_tipo_res.setStyleSheet("color: #94a3b8; font-size: 12px;")
        col_meta.addWidget(self.lbl_midia_tipo_res)

        self.lbl_midia_detalhes = QLabel("")
        self.lbl_midia_detalhes.setStyleSheet("color: #64748b; font-size: 11px;")
        col_meta.addWidget(self.lbl_midia_detalhes)

        col_meta.addStretch()

        self.btn_ver_midia_inteira = QPushButton("🔍 Visualizar Mídia Completa")
        self.btn_ver_midia_inteira.setFixedWidth(200)
        self.btn_ver_midia_inteira.setVisible(False)
        self.btn_ver_midia_inteira.clicked.connect(self._abrir_visualizador_midia_completa)
        col_meta.addWidget(self.btn_ver_midia_inteira)

        layout_preview_midia.addLayout(col_meta, stretch=1)
        self.layout_principal.addWidget(self.frame_preview_midia)

        # Atualiza a miniatura automaticamente ao alterar o caminho
        self.input_caminho_midia.textChanged.connect(self._atualizar_preview_midia)

        # --- Seção 2: Narração Neural com edge-tts ---
        narracao_box = QVBoxLayout()
        narracao_header = QHBoxLayout()
        narracao_label = QLabel("🎙️ Narração Neural com IA (edge-tts):")
        narracao_label.setStyleSheet("font-weight: 600; color: #93c5fd;")
        narracao_header.addWidget(narracao_label)
        narracao_header.addStretch()

        self.combo_voz = QComboBox()
        self.combo_voz.setItemDelegate(QStyledItemDelegate(self.combo_voz))
        self.combo_voz.addItem("Voz Padrão do Projeto", None)
        for rotulo, val in OPCOES_VOZES.items():
            if val != "custom":
                self.combo_voz.addItem(rotulo, val)
        self.combo_voz.setFixedWidth(280)
        narracao_header.addWidget(self.combo_voz)

        self.combo_taxa = QComboBox()
        self.combo_taxa.setItemDelegate(QStyledItemDelegate(self.combo_taxa))
        self.combo_taxa.addItem("Velocidade Padrão", None)
        for taxa in TAXAS_FALA:
            self.combo_taxa.addItem(taxa, taxa)
        self.combo_taxa.setFixedWidth(140)
        narracao_header.addWidget(self.combo_taxa)

        self.btn_ouvir_audio = QPushButton("🔊 Ouvir Prévia")
        self.btn_ouvir_audio.setToolTip("Sintetiza e reproduz o áudio desta cena diretamente dentro do aplicativo")
        self.btn_ouvir_audio.clicked.connect(self._ouvir_previa_audio)
        narracao_header.addWidget(self.btn_ouvir_audio)

        narracao_box.addLayout(narracao_header)

        self.input_narracao = QTextEdit()
        self.input_narracao.setPlaceholderText("Digite o texto que a voz neural irá narrar para esta cena...")
        self.input_narracao.setMaximumHeight(70)
        narracao_box.addWidget(self.input_narracao)

        self.layout_principal.addLayout(narracao_box)

        # --- Seção 3: Legendas e Tarja de Texto ---
        extras_layout = QGridLayout()

        # Legenda discreta
        self.check_legenda = QCheckBox("Exibir Legenda Discreta no Rodapé")
        self.check_legenda.setChecked(True)
        extras_layout.addWidget(self.check_legenda, 0, 0)

        legenda_input_layout = QHBoxLayout()
        self.input_legenda = QLineEdit()
        self.input_legenda.setPlaceholderText("Texto da legenda (deixe em branco para usar o texto da narração)...")
        legenda_input_layout.addWidget(self.input_legenda, stretch=1)

        self.btn_copiar_narracao = QPushButton("📋 Copiar Narração")
        self.btn_copiar_narracao.setToolTip("Copia o texto da narração para a legenda")
        self.btn_copiar_narracao.clicked.connect(
            lambda: self.input_legenda.setText(self.input_narracao.toPlainText().strip())
        )
        legenda_input_layout.addWidget(self.btn_copiar_narracao)
        extras_layout.addLayout(legenda_input_layout, 0, 1)

        # Tarja de texto visual (lower-third)
        self.check_tarja = QCheckBox("Exibir Tarja de Título (Lower-Third)")
        self.check_tarja.setChecked(True)
        extras_layout.addWidget(self.check_tarja, 1, 0)

        self.input_tarja = QLineEdit()
        self.input_tarja.setPlaceholderText("Texto da tarja estilizada (deixe vazio para usar o título da cena)...")
        extras_layout.addWidget(self.input_tarja, 1, 1)

        self.layout_principal.addLayout(extras_layout)

        # --- Rodapé do Card: Prévia Visual ---
        footer_layout = QHBoxLayout()
        footer_layout.addStretch()

        self.btn_preview_frame = QPushButton("🖼️ Visualizar Prévia do Frame (Snapshot)")
        self.btn_preview_frame.clicked.connect(self._abrir_previa_frame)
        footer_layout.addWidget(self.btn_preview_frame)

        self.layout_principal.addLayout(footer_layout)

    def atualizar_numero(self, novo_numero: int):
        self.numero = novo_numero
        self.badge_num.setText(f"Cena {self.numero:02d}")

    def _abrir_seletor_midia(self):
        caminho, _ = QFileDialog.getOpenFileName(
            self,
            "Selecionar Gravação de Tela ou Imagem",
            str(Path.cwd()),
            "Mídias Suportadas (*.mp4 *.webm *.mkv *.avi *.mov *.png *.jpg *.jpeg *.webp);;Vídeos (*.mp4 *.webm *.mkv *.avi *.mov);;Imagens (*.png *.jpg *.jpeg *.webp);;Todos os Arquivos (*)",
        )
        if caminho:
            self.input_caminho_midia.setText(caminho)

    def _atualizar_preview_midia(self):
        caminho = self.input_caminho_midia.text().strip()
        info_midia = gerar_miniatura_midia(caminho, largura_max=190, altura_max=108)
        if info_midia:
            img_pil, nome, tipo_res, detalhes = info_midia
            img_bytes = img_pil.convert("RGBA").tobytes("raw", "RGBA")
            qim = QImage(img_bytes, img_pil.width, img_pil.height, QImage.Format_RGBA8888)
            pix = QPixmap.fromImage(qim)
            self.lbl_thumb_midia.setPixmap(pix)
            self.lbl_thumb_midia.setText("")
            self.lbl_thumb_midia.setStyleSheet(
                "background-color: #090d16; border: 1px solid #3b82f6; border-radius: 6px;"
            )
            self.lbl_midia_nome.setText(nome)
            self.lbl_midia_tipo_res.setText(tipo_res)
            self.lbl_midia_detalhes.setText(detalhes)
            self.btn_ver_midia_inteira.setVisible(True)
        else:
            self.lbl_thumb_midia.clear()
            self.lbl_thumb_midia.setText("📷 Sem Mídia")
            self.lbl_thumb_midia.setStyleSheet(
                "background-color: #111827; border: 1px dashed #374151; border-radius: 6px; color: #64748b;"
            )
            self.lbl_midia_nome.setText("Nenhuma mídia selecionada")
            self.lbl_midia_tipo_res.setText("Clique em '📁 Procurar...' para carregar um vídeo ou captura de tela.")
            self.lbl_midia_detalhes.setText("")
            self.btn_ver_midia_inteira.setVisible(False)

    def _abrir_visualizador_midia_completa(self):
        caminho = self.input_caminho_midia.text().strip()
        if caminho and Path(caminho).is_file():
            dlg = MediaViewerDialog(caminho, self.input_titulo.text().strip(), self)
            dlg.exec()

    def _abrir_previa_frame(self):
        caminho_midia = self.input_caminho_midia.text().strip()
        if not caminho_midia or not Path(caminho_midia).is_file():
            QMessageBox.warning(
                self,
                "Mídia Ausente",
                "Selecione um arquivo de vídeo ou captura de tela válido antes de gerar a prévia visual.",
            )
            return

        texto_tarja = self.input_tarja.text().strip() or self.input_titulo.text().strip()
        texto_fala = self.input_narracao.toPlainText().strip()
        texto_legenda = self.input_legenda.text().strip() or texto_fala

        try:
            # Obtém a resolução da janela principal se disponível
            resolucao = (1920, 1080)
            janela = self.window()
            if hasattr(janela, "obter_resolucao_ativa"):
                resolucao = janela.obter_resolucao_ativa()

            img_composta = gerar_previa_frame_composto(
                caminho_midia=caminho_midia,
                texto_tarja=texto_tarja,
                texto_legenda=texto_legenda,
                exibir_tarja=self.check_tarja.isChecked(),
                exibir_legenda=self.check_legenda.isChecked(),
                resolucao=resolucao,
            )

            dialog = FramePreviewDialog(img_composta, self.input_titulo.text().strip(), self)
            dialog.exec()
        except Exception as e:
            QMessageBox.critical(self, "Erro na Prévia", f"Falha ao gerar prévia do frame:\n{e}")

    def _ouvir_previa_audio(self):
        # Se já estiver reproduzindo o áudio interno, interrompe a execução
        if self.player.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
            self.player.stop()
            self.btn_ouvir_audio.setText("🔊 Ouvir Prévia")
            self.btn_ouvir_audio.setStyleSheet("")
            return

        texto = self.input_narracao.toPlainText().strip()
        if not texto:
            QMessageBox.information(
                self,
                "Texto de Narração Ausente",
                "Digite um texto no campo de narração desta cena para ouvir a prévia neural.",
            )
            return

        janela = self.window()
        voz_padrao = "pt-BR-AntonioNeural"
        taxa_padrao = "+0%"
        if hasattr(janela, "obter_voz_padrao"):
            voz_padrao = janela.obter_voz_padrao()
        if hasattr(janela, "obter_taxa_padrao"):
            taxa_padrao = janela.obter_taxa_padrao()

        voz = self.combo_voz.currentData() or voz_padrao
        taxa = self.combo_taxa.currentData() or taxa_padrao

        self.btn_ouvir_audio.setEnabled(False)
        self.btn_ouvir_audio.setText("⏳ Gerando...")
        QApplication.processEvents()

        pasta_temp = Path("temp_desktop/audios_previa")
        arq_saida = pasta_temp / f"previa_{self.uid}_{int(time.time())}.mp3"

        sucesso = sintetizar_audio_sincrono(texto, arq_saida, voz, taxa)
        self.btn_ouvir_audio.setEnabled(True)

        if sucesso and arq_saida.is_file():
            # Reproduz diretamente DENTRO da aplicação com o QMediaPlayer integrado
            self.player.setSource(QUrl.fromLocalFile(str(arq_saida.resolve())))
            self.player.play()
            self.btn_ouvir_audio.setText("⏹️ Parar Áudio")
            self.btn_ouvir_audio.setStyleSheet(
                "background-color: #991b1b; color: #ffffff; border: 1px solid #ef4444;"
            )
        else:
            self.btn_ouvir_audio.setText("🔊 Ouvir Prévia")
            self.btn_ouvir_audio.setStyleSheet("")
            QMessageBox.critical(
                self,
                "Erro de Síntese",
                "Não foi possível sintetizar o áudio com o Microsoft Edge TTS.\nVerifique sua conexão com a internet.",
            )

    def _ao_mudar_estado_player(self, estado):
        if estado != QMediaPlayer.PlaybackState.PlayingState:
            self.btn_ouvir_audio.setText("🔊 Ouvir Prévia")
            self.btn_ouvir_audio.setStyleSheet("")


    def obter_dados(self) -> Dict[str, Any]:
        """Extrai todos os dados preenchidos neste card."""
        return {
            "id": f"passo_{self.numero:02d}",
            "uid": self.uid,
            "numero": self.numero,
            "titulo": self.input_titulo.text().strip() or f"Cena {self.numero}",
            "caminho_midia": self.input_caminho_midia.text().strip(),
            "texto_narracao": self.input_narracao.toPlainText().strip(),
            "voz": self.combo_voz.currentData(),
            "taxa_fala": self.combo_taxa.currentData(),
            "exibir_legenda": self.check_legenda.isChecked(),
            "legenda": self.input_legenda.text().strip(),
            "exibir_overlay": self.check_tarja.isChecked(),
            "tarja_visual": self.input_tarja.text().strip(),
        }

    def preencher_dados(self, dados: Dict[str, Any]):
        """Popula os campos do card a partir de um dicionário."""
        if "titulo" in dados:
            self.input_titulo.setText(str(dados["titulo"]))
        if "video_path" in dados:
            self.input_caminho_midia.setText(str(dados["video_path"]))
        elif "caminho_midia" in dados:
            self.input_caminho_midia.setText(str(dados["caminho_midia"]))
        if "texto_narracao" in dados:
            self.input_narracao.setPlainText(str(dados["texto_narracao"]))
        if "tarja_visual" in dados:
            self.input_tarja.setText(str(dados["tarja_visual"]))
        elif "overlay_texto" in dados and isinstance(dados["overlay_texto"], dict):
            self.input_tarja.setText(str(dados["overlay_texto"].get("texto", "")))
        if "legenda" in dados and dados["legenda"]:
            self.input_legenda.setText(str(dados["legenda"]))
        if "exibir_legenda" in dados:
            self.check_legenda.setChecked(bool(dados["exibir_legenda"]))
        if "exibir_overlay" in dados:
            self.check_tarja.setChecked(bool(dados["exibir_overlay"]))


# ==============================================================================
# Thread Assíncrona de Renderização e Geração de Vídeo
# ==============================================================================

class RenderWorkerThread(QThread):
    """Thread desacoplada para processar voz e renderizar vídeo com MoviePy sem travar a UI."""

    progresso = Signal(int, str)       # (porcentagem 0-100, mensagem_status)
    log_msg = Signal(str, str)         # (mensagem, nivel: 'info', 'sucesso', 'erro')
    concluido = Signal(str, float)     # (caminho_video_saida, duracao_segundos)
    falhou = Signal(str)               # (mensagem_erro)

    def __init__(self, titulo_projeto: str, config_geral: Dict[str, Any], cenas: List[Dict[str, Any]], parent=None):
        super().__init__(parent)
        self.titulo_projeto = titulo_projeto
        self.config_geral = config_geral
        self.cenas = cenas
        self._cancelado = False

    def cancelar(self):
        self._cancelado = True

    def run(self):
        clipes_para_fechar = []
        try:
            self.log_msg.emit("🚀 Iniciando pipeline de geração de vídeo tutorial...", "info")
            self.progresso.emit(2, "Iniciando processamento...")

            timestamp = int(time.time())
            pasta_trabalho = Path("temp_desktop") / f"job_{timestamp}"
            pasta_uploads = pasta_trabalho / "uploads"
            pasta_audios = pasta_trabalho / "audios"
            pasta_saida = Path("saida")

            pasta_uploads.mkdir(parents=True, exist_ok=True)
            pasta_audios.mkdir(parents=True, exist_ok=True)
            pasta_saida.mkdir(parents=True, exist_ok=True)

            nome_seguro = sanitizar_nome_arquivo(self.titulo_projeto)
            caminho_video_final = pasta_saida / f"{nome_seguro}_{timestamp}.mp4"

            total_cenas = len(self.cenas)
            voz_padrao = self.config_geral.get("voz_padrao", "pt-BR-AntonioNeural")
            taxa_padrao = self.config_geral.get("taxa_fala_padrao", "+0%")
            resolucao_padrao = tuple(self.config_geral.get("resolucao_padrao", (1920, 1080)))
            fps_padrao = int(self.config_geral.get("fps_padrao", 30))
            pausa_final_padrao = float(self.config_geral.get("pausa_final_padrao", 0.5))

            # Validação e cópia de mídias para a pasta do job
            self.log_msg.emit(f"📥 Organizando {total_cenas} arquivos de mídia das cenas...", "info")
            cenas_prontas: List[Tuple[Cena, Path]] = []

            for c in self.cenas:
                if self._cancelado:
                    raise InterruptedError("Operação cancelada pelo usuário.")

                midia_orig = Path(c["caminho_midia"])
                if not midia_orig.is_file():
                    raise FileNotFoundError(f"Arquivo de mídia da {c['titulo']} não encontrado: {midia_orig}")

                ext = midia_orig.suffix.lower()
                caminho_midia_job = pasta_uploads / f"{c['id']}{ext}"
                shutil.copyfile(midia_orig, caminho_midia_job)

                texto_tarja = c.get("tarja_visual", "").strip() or c["titulo"]
                overlay_cfg = (
                    OverlayTextoConfig(texto=texto_tarja, posicao="inferior_esquerdo")
                    if (c["exibir_overlay"] and texto_tarja)
                    else None
                )

                texto_fala = c["texto_narracao"] if c["texto_narracao"] else c.get("legenda", "")
                texto_legenda_final = c.get("legenda", "").strip() or texto_fala
                exibir_legenda_final = bool(c.get("exibir_legenda", True)) and bool(texto_legenda_final)

                cena_obj = Cena(
                    id=c["id"],
                    titulo=c["titulo"],
                    video_path=caminho_midia_job,
                    texto_narracao=texto_fala,
                    voz=c.get("voz") or voz_padrao,
                    taxa_fala=c.get("taxa_fala") or taxa_padrao,
                    overlay_texto=overlay_cfg,
                    imagem_destaque=None,
                    pausa_final=pausa_final_padrao,
                    legenda=texto_legenda_final,
                    tarja_visual=texto_tarja,
                    exibir_legenda=exibir_legenda_final,
                )
                cenas_prontas.append((cena_obj, caminho_midia_job))

            cfg_geral_obj = ConfiguracaoGeral(
                voz_padrao=voz_padrao,
                taxa_fala_padrao=taxa_padrao,
                volume_padrao="+0%",
                resolucao_padrao=resolucao_padrao,
                fps_padrao=fps_padrao,
                pausa_final_padrao=pausa_final_padrao,
                video_saida=caminho_video_final,
                manter_audios_temp=False,
            )

            # ------------------------------------------------------------------
            # ETAPA 1: Síntese de Voz com edge-tts (0% a 35%)
            # ------------------------------------------------------------------
            self.log_msg.emit("🎙️ [Etapa 1/3] Sintetizando narrações neurais com edge-tts...", "info")
            arquivos_audio: List[Path] = []

            for i, (cena_obj, _) in enumerate(cenas_prontas, 1):
                if self._cancelado:
                    raise InterruptedError("Operação cancelada pelo usuário.")

                caminho_audio = pasta_audios / f"{cena_obj.id}.mp3"
                arquivos_audio.append(caminho_audio)

                self.log_msg.emit(f"   🔊 Voz neural para Cena {i}/{total_cenas}: '{cena_obj.titulo}'...", "info")

                sucesso = sintetizar_audio_sincrono(
                    texto=cena_obj.texto_narracao,
                    caminho_saida=caminho_audio,
                    voz=cena_obj.voz or voz_padrao,
                    taxa=cena_obj.taxa_fala or taxa_padrao,
                )
                if not sucesso:
                    raise RuntimeError(f"Falha ao sintetizar áudio da cena '{cena_obj.titulo}'.")

                pct = int((i / total_cenas) * 35)
                self.progresso.emit(pct, f"Síntese de voz: Cena {i}/{total_cenas}")

            # ------------------------------------------------------------------
            # ETAPA 2: Edição e Composição com MoviePy (35% a 75%)
            # ------------------------------------------------------------------
            self.log_msg.emit("🎞️ [Etapa 2/3] Sincronizando vídeo, áudio, legendas e tarjas com MoviePy...", "info")
            clipes_processados = []

            for i, ((cena_obj, _), arq_audio) in enumerate(zip(cenas_prontas, arquivos_audio), 1):
                if self._cancelado:
                    raise InterruptedError("Operação cancelada pelo usuário.")

                self.log_msg.emit(f"   ⚙️ Processando clipes da Cena {i}/{total_cenas} ({resolucao_padrao[0]}x{resolucao_padrao[1]})...", "info")

                clipe = processar_cena_individual(
                    cena=cena_obj,
                    caminho_audio=arq_audio,
                    config_geral=cfg_geral_obj,
                )
                clipes_processados.append(clipe)
                clipes_para_fechar.append(clipe)

                pct = 35 + int((i / total_cenas) * 40)
                self.progresso.emit(pct, f"Composição visual: Cena {i}/{total_cenas}")

            # ------------------------------------------------------------------
            # ETAPA 3: Concatenação e Codificação Final MP4 (75% a 100%)
            # ------------------------------------------------------------------
            if self._cancelado:
                raise InterruptedError("Operação cancelada pelo usuário.")

            self.log_msg.emit("🎬 [Etapa 3/3] Concatenando cenas e renderizando vídeo final...", "info")
            self.progresso.emit(78, "Concatenando sequências de vídeo...")

            video_completo = concatenate_videoclips(clipes_processados, method="compose")
            clipes_para_fechar.append(video_completo)

            duracao_total = float(video_completo.duration or 0.0)
            self.log_msg.emit(f"   ⏱️ Duração calculada do tutorial: {duracao_total:.1f} segundos", "info")
            self.log_msg.emit(f"   🎥 Codificando arquivo final: {caminho_video_final.name} (H.264/AAC)...", "info")

            self.progresso.emit(85, "Renderizando arquivo MP4 final...")

            video_completo.write_videofile(
                str(caminho_video_final),
                fps=fps_padrao,
                codec="libx264",
                audio_codec="aac",
                preset="medium",
                threads=4,
                logger=None,
            )

            self.progresso.emit(100, "Concluído!")
            self.log_msg.emit(f"🎉 Vídeo gerado com sucesso: {caminho_video_final}", "sucesso")
            self.concluido.emit(str(caminho_video_final), duracao_total)

        except InterruptedError:
            self.log_msg.emit("⚠️ Geração cancelada pelo usuário.", "alerta")
            self.falhou.emit("Geração cancelada.")
        except Exception as e:
            self.log_msg.emit(f"❌ Erro fatal durante a renderização: {e}", "erro")
            self.falhou.emit(str(e))
        finally:
            # Fecha todos os clipes para liberar ponteiros de arquivos e recursos de sistema
            for c in clipes_para_fechar:
                try:
                    c.close()
                except Exception:
                    pass


# ==============================================================================
# Janela Principal (MainWindow)
# ==============================================================================

class MainWindow(QMainWindow):
    """Janela principal da aplicação Desktop."""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Gerador Automático de Tutoriais em Vídeo com IA")
        self.resize(1280, 850)
        self.setMinimumSize(1000, 700)
        self.setStyleSheet(ESTILO_QSS)

        self.cards_cenas: List[SceneCardWidget] = []
        self.scene_counter = 0
        self.thread_renderizacao: Optional[RenderWorkerThread] = None
        self.ultimo_video_gerado: Optional[str] = None

        self._construir_ui()
        self._carregar_projeto_inicial()

    def _construir_ui(self):
        widget_central = QWidget()
        widget_central.setObjectName("CentralWidget")
        self.setCentralWidget(widget_central)

        layout_raiz = QVBoxLayout(widget_central)
        layout_raiz.setContentsMargins(16, 16, 16, 16)
        layout_raiz.setSpacing(12)

        # ----------------------------------------------------------------------
        # Topo: Cabeçalho com Título e Botões Globais de Arquivo
        # ----------------------------------------------------------------------
        header_frame = QFrame()
        header_layout = QHBoxLayout(header_frame)
        header_layout.setContentsMargins(0, 0, 0, 8)

        titulo_box = QVBoxLayout()
        lbl_titulo = QLabel("🎬 Gerador Automático de Tutoriais em Vídeo")
        lbl_titulo.setProperty("class", "title-label")
        lbl_subtitulo = QLabel("Crie tutoriais profissionais com narração neural de alta fidelidade e sincronização automática.")
        lbl_subtitulo.setStyleSheet("color: #94a3b8; font-size: 12px;")
        titulo_box.addWidget(lbl_titulo)
        titulo_box.addWidget(lbl_subtitulo)
        header_layout.addLayout(titulo_box, stretch=1)

        # Botões de Ação do Projeto
        btn_novo = QPushButton("✨ Novo")
        btn_novo.setToolTip("Iniciar um novo projeto limpo")
        btn_novo.clicked.connect(self._acao_novo_projeto)
        header_layout.addWidget(btn_novo)

        btn_carregar_json = QPushButton("📂 Carregar JSON")
        btn_carregar_json.setToolTip("Carregar projeto a partir de um arquivo .json")
        btn_carregar_json.clicked.connect(self._acao_carregar_json)
        header_layout.addWidget(btn_carregar_json)

        btn_importar_zip = QPushButton("📦 Importar ZIP")
        btn_importar_zip.setToolTip("Importar pacote completo ZIP com vídeos e prints")
        btn_importar_zip.clicked.connect(self._acao_importar_zip)
        header_layout.addWidget(btn_importar_zip)

        btn_salvar_json = QPushButton("💾 Salvar JSON")
        btn_salvar_json.setToolTip("Salvar configuração em arquivo .json")
        btn_salvar_json.clicked.connect(self._acao_salvar_json)
        header_layout.addWidget(btn_salvar_json)

        btn_exportar_zip = QPushButton("📦 Exportar ZIP")
        btn_exportar_zip.setToolTip("Exportar pacote ZIP completo com mídias e JSON")
        btn_exportar_zip.clicked.connect(self._acao_exportar_zip)
        header_layout.addWidget(btn_exportar_zip)

        layout_raiz.addWidget(header_frame)

        # ----------------------------------------------------------------------
        # Corpo Principal Dividido em Duas Colunas (Splitter)
        # ----------------------------------------------------------------------
        splitter = QSplitter(Qt.Horizontal)

        # Coluna Esquerda: Configurações Gerais da Aplicação
        sidebar_frame = QFrame()
        sidebar_frame.setProperty("class", "card-frame sidebar-frame")
        sidebar_frame.setMinimumWidth(320)
        sidebar_frame.setMaximumWidth(400)
        sidebar_layout = QVBoxLayout(sidebar_frame)
        sidebar_layout.setSpacing(12)

        lbl_cfg = QLabel("⚙️ Configurações Gerais")
        lbl_cfg.setStyleSheet("font-size: 15px; font-weight: bold; color: #60a5fa;")
        sidebar_layout.addWidget(lbl_cfg)

        # Nome do Projeto
        sidebar_layout.addWidget(QLabel("📌 Nome do Projeto / Vídeo:"))
        self.input_titulo_projeto = QLineEdit("Meu Vídeo Tutorial")
        sidebar_layout.addWidget(self.input_titulo_projeto)

        # Resolução
        sidebar_layout.addWidget(QLabel("📐 Resolução de Saída:"))
        self.combo_resolucao = QComboBox()
        self.combo_resolucao.setItemDelegate(QStyledItemDelegate(self.combo_resolucao))
        for rotulo, res in OPCOES_RESOLUCAO.items():
            self.combo_resolucao.addItem(rotulo, res)
        sidebar_layout.addWidget(self.combo_resolucao)

        # FPS
        sidebar_layout.addWidget(QLabel("🎞️ Taxa de Quadros (FPS):"))
        self.combo_fps = QComboBox()
        self.combo_fps.setItemDelegate(QStyledItemDelegate(self.combo_fps))
        self.combo_fps.addItems(["30 FPS (Padrão Recomendado)", "60 FPS (Alta Fluidez)", "24 FPS (Cinemático)"])
        sidebar_layout.addWidget(self.combo_fps)

        # Voz Padrão do Projeto
        sidebar_layout.addWidget(QLabel("🗣️ Voz Padrão (edge-tts):"))
        self.combo_voz_padrao = QComboBox()
        self.combo_voz_padrao.setItemDelegate(QStyledItemDelegate(self.combo_voz_padrao))
        for rotulo, val in OPCOES_VOZES.items():
            if val != "custom":
                self.combo_voz_padrao.addItem(rotulo, val)
        sidebar_layout.addWidget(self.combo_voz_padrao)

        # Velocidade Padrão
        sidebar_layout.addWidget(QLabel("⚡ Velocidade da Fala Padrão:"))
        self.combo_taxa_padrao = QComboBox()
        self.combo_taxa_padrao.setItemDelegate(QStyledItemDelegate(self.combo_taxa_padrao))
        for taxa in TAXAS_FALA:
            self.combo_taxa_padrao.addItem(taxa, taxa)
        self.combo_taxa_padrao.setCurrentText("+0%")
        sidebar_layout.addWidget(self.combo_taxa_padrao)


        # Pausa Final
        sidebar_layout.addWidget(QLabel("⏸️ Pausa Final entre Cenas (segundos):"))
        self.spin_pausa = QDoubleSpinBox()
        self.spin_pausa.setRange(0.0, 5.0)
        self.spin_pausa.setSingleStep(0.2)
        self.spin_pausa.setValue(0.5)
        sidebar_layout.addWidget(self.spin_pausa)

        sidebar_layout.addStretch()

        # Botão Limpar Cache
        btn_limpar_cache = QPushButton("🧹 Limpar Arquivos Temporários")
        btn_limpar_cache.setToolTip("Remove arquivos temporários de jobs anteriores")
        btn_limpar_cache.clicked.connect(self._acao_limpar_temporarios)
        sidebar_layout.addWidget(btn_limpar_cache)

        splitter.addWidget(sidebar_frame)

        # Coluna Direita: Gerenciador de Cenas + Painel de Renderização
        painel_direito = QWidget()
        painel_direito_layout = QVBoxLayout(painel_direito)
        painel_direito_layout.setContentsMargins(0, 0, 0, 0)
        painel_direito_layout.setSpacing(10)

        # Barra de Cenas
        cenas_header = QHBoxLayout()
        lbl_cenas = QLabel("📑 Cenas do Tutorial")
        lbl_cenas.setStyleSheet("font-size: 15px; font-weight: bold; color: #93c5fd;")
        cenas_header.addWidget(lbl_cenas)
        cenas_header.addStretch()

        self.btn_add_cena = QPushButton("➕ Adicionar Nova Cena")
        self.btn_add_cena.clicked.connect(self._adicionar_nova_cena)
        cenas_header.addWidget(self.btn_add_cena)
        painel_direito_layout.addLayout(cenas_header)

        # Scroll Area com a lista de cards de cenas
        self.scroll_cenas = QScrollArea()
        self.scroll_cenas.setWidgetResizable(True)
        self.container_cenas = QWidget()
        self.layout_cenas = QVBoxLayout(self.container_cenas)
        self.layout_cenas.setContentsMargins(0, 0, 0, 0)
        self.layout_cenas.setSpacing(10)
        self.layout_cenas.addStretch()
        self.scroll_cenas.setWidget(self.container_cenas)
        painel_direito_layout.addWidget(self.scroll_cenas, stretch=1)

        # ----------------------------------------------------------------------
        # Painel Inferior: Execução, Progresso e Terminal de Logs
        # ----------------------------------------------------------------------
        exec_frame = QFrame()
        exec_frame.setProperty("class", "card-frame")
        exec_layout = QVBoxLayout(exec_frame)
        exec_layout.setSpacing(8)

        # Linha de botões de execução
        exec_btns_layout = QHBoxLayout()
        self.btn_gerar = QPushButton("🚀 Gerar Vídeo Tutorial")
        self.btn_gerar.setProperty("class", "primary-btn")
        self.btn_gerar.clicked.connect(self._iniciar_geracao_video)
        exec_btns_layout.addWidget(self.btn_gerar, stretch=1)

        self.btn_cancelar = QPushButton("🛑 Cancelar")
        self.btn_cancelar.setProperty("class", "danger-btn")
        self.btn_cancelar.setEnabled(False)
        self.btn_cancelar.clicked.connect(self._cancelar_geracao_video)
        exec_btns_layout.addWidget(self.btn_cancelar)

        exec_layout.addLayout(exec_btns_layout)

        # Barra de Progresso
        self.progress_bar = QProgressBar()
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(True)
        exec_layout.addWidget(self.progress_bar)

        self.lbl_status = QLabel("Pronto para iniciar.")
        self.lbl_status.setStyleSheet("color: #94a3b8; font-size: 11px;")
        exec_layout.addWidget(self.lbl_status)

        # Terminal de Logs em tempo real
        self.log_console = QTextEdit()
        self.log_console.setProperty("class", "log-console")
        self.log_console.setReadOnly(True)
        self.log_console.setMaximumHeight(110)
        exec_layout.addWidget(self.log_console)

        # Painel de Conclusão / Resultado (exibido após renderização com sucesso)
        self.painel_resultado = QFrame()
        self.painel_resultado.setStyleSheet("background-color: #064e3b; border-radius: 8px; padding: 8px;")
        self.painel_resultado.setVisible(False)
        resultado_layout = QHBoxLayout(self.painel_resultado)

        self.lbl_resultado_info = QLabel("🎉 Vídeo gerado com sucesso!")
        self.lbl_resultado_info.setStyleSheet("color: #d1fae5; font-weight: bold;")
        resultado_layout.addWidget(self.lbl_resultado_info, stretch=1)

        btn_abrir_video = QPushButton("▶️ Abrir Vídeo")
        btn_abrir_video.clicked.connect(self._abrir_video_gerado)
        resultado_layout.addWidget(btn_abrir_video)

        btn_abrir_pasta = QPushButton("📁 Abrir Pasta")
        btn_abrir_pasta.clicked.connect(self._abrir_pasta_saida)
        resultado_layout.addWidget(btn_abrir_pasta)

        btn_salvar_copia = QPushButton("💾 Salvar Como...")
        btn_salvar_copia.clicked.connect(self._salvar_copia_video)
        resultado_layout.addWidget(btn_salvar_copia)

        exec_layout.addWidget(self.painel_resultado)

        painel_direito_layout.addWidget(exec_frame)
        splitter.addWidget(painel_direito)
        splitter.setSizes([340, 940])

        layout_raiz.addWidget(splitter, stretch=1)

    # ==========================================================================
    # Métodos de Gerenciamento de Cenas
    # ==========================================================================

    def _adicionar_nova_cena(self, dados_iniciais: Optional[Dict[str, Any]] = None) -> SceneCardWidget:
        self.scene_counter += 1
        uid = f"scene_{self.scene_counter}_{int(time.time()*1000)}"
        card = SceneCardWidget(uid=uid, numero=len(self.cards_cenas) + 1, parent=self.container_cenas)

        card.solicitar_reordenar.connect(self._reordenar_cena)
        card.solicitar_excluir.connect(self._excluir_cena)
        card.solicitar_duplicar.connect(self._duplicar_cena)

        if dados_iniciais:
            card.preencher_dados(dados_iniciais)

        self.cards_cenas.append(card)
        # Insere antes do stretch
        self.layout_cenas.insertWidget(self.layout_cenas.count() - 1, card)
        self._renumerar_cenas()
        return card

    def _renumerar_cenas(self):
        for idx, card in enumerate(self.cards_cenas, 1):
            card.atualizar_numero(idx)

    def _reordenar_cena(self, uid: str, direcao: str):
        indices = [i for i, c in enumerate(self.cards_cenas) if c.uid == uid]
        if not indices:
            return
        idx = indices[0]

        if direcao == "cima" and idx > 0:
            self.cards_cenas[idx], self.cards_cenas[idx - 1] = self.cards_cenas[idx - 1], self.cards_cenas[idx]
        elif direcao == "baixo" and idx < len(self.cards_cenas) - 1:
            self.cards_cenas[idx], self.cards_cenas[idx + 1] = self.cards_cenas[idx + 1], self.cards_cenas[idx]

        # Reconstrói a ordem na tela
        for card in self.cards_cenas:
            self.layout_cenas.removeWidget(card)
        for card in self.cards_cenas:
            self.layout_cenas.insertWidget(self.layout_cenas.count() - 1, card)

        self._renumerar_cenas()

    def _excluir_cena(self, uid: str):
        if len(self.cards_cenas) <= 1:
            QMessageBox.warning(self, "Aviso", "O tutorial precisa ter no mínimo 1 cena.")
            return

        indices = [i for i, c in enumerate(self.cards_cenas) if c.uid == uid]
        if indices:
            idx = indices[0]
            card = self.cards_cenas.pop(idx)
            self.layout_cenas.removeWidget(card)
            card.deleteLater()
            self._renumerar_cenas()

    def _duplicar_cena(self, uid: str):
        for c in self.cards_cenas:
            if c.uid == uid:
                dados = c.obter_dados()
                dados["titulo"] = f"{dados['titulo']} (Cópia)"
                self._adicionar_nova_cena(dados)
                break

    # ==========================================================================
    # Getters de Configuração Geral
    # ==========================================================================

    def obter_resolucao_ativa(self) -> Tuple[int, int]:
        return self.combo_resolucao.currentData() or (1920, 1080)

    def obter_fps_ativo(self) -> int:
        txt = self.combo_fps.currentText()
        if "60" in txt:
            return 60
        elif "24" in txt:
            return 24
        return 30

    def obter_voz_padrao(self) -> str:
        return self.combo_voz_padrao.currentData() or "pt-BR-AntonioNeural"

    def obter_taxa_padrao(self) -> str:
        return self.combo_taxa_padrao.currentData() or "+0%"

    def obter_config_geral_dict(self) -> Dict[str, Any]:
        return {
            "voz_padrao": self.obter_voz_padrao(),
            "taxa_fala_padrao": self.obter_taxa_padrao(),
            "volume_padrao": "+0%",
            "resolucao_padrao": list(self.obter_resolucao_ativa()),
            "fps_padrao": self.obter_fps_ativo(),
            "pausa_final_padrao": float(self.spin_pausa.value()),
            "manter_audios_temp": False,
        }

    # ==========================================================================
    # Ações de Projeto (Novo, Salvar, Carregar, Exportar, Importar)
    # ==========================================================================

    def _carregar_projeto_inicial(self):
        """Carrega o exemplo se existir ou cria uma cena vazia."""
        exemplo = Path("config_exemplo.json")
        if exemplo.is_file():
            try:
                self._carregar_projeto_de_arquivo(exemplo)
                return
            except Exception:
                pass
        self._adicionar_nova_cena()

    def _acao_novo_projeto(self):
        resp = QMessageBox.question(
            self,
            "Novo Projeto",
            "Deseja limpar todos os dados e criar um novo projeto em branco?",
            QMessageBox.Yes | QMessageBox.No,
        )
        if resp == QMessageBox.Yes:
            self._limpar_todas_cenas()
            self.input_titulo_projeto.setText("Meu Vídeo Tutorial")
            self.combo_resolucao.setCurrentIndex(0)
            self.combo_fps.setCurrentIndex(0)
            self.combo_voz_padrao.setCurrentIndex(0)
            self.combo_taxa_padrao.setCurrentText("+0%")
            self.spin_pausa.setValue(0.5)
            self._adicionar_nova_cena()
            self.painel_resultado.setVisible(False)
            self.progress_bar.setValue(0)
            self.lbl_status.setText("Novo projeto inicializado.")
            self.log_console.clear()

    def _limpar_todas_cenas(self):
        for card in self.cards_cenas:
            self.layout_cenas.removeWidget(card)
            card.deleteLater()
        self.cards_cenas.clear()
        self.scene_counter = 0

    def _acao_salvar_json(self):
        caminho, _ = QFileDialog.getSaveFileName(
            self,
            "Salvar Projeto JSON",
            str(Path.cwd() / "config_projeto.json"),
            "Arquivo de Configuração JSON (*.json)",
        )
        if caminho:
            try:
                cenas = [c.obter_dados() for c in self.cards_cenas]
                salvar_projeto_json(
                    caminho_arquivo=Path(caminho),
                    titulo=self.input_titulo_projeto.text().strip(),
                    config_geral=self.obter_config_geral_dict(),
                    cenas=cenas,
                )
                QMessageBox.information(self, "Sucesso", f"Projeto salvo com sucesso em:\n{caminho}")
            except Exception as e:
                QMessageBox.critical(self, "Erro", f"Falha ao salvar projeto:\n{e}")

    def _acao_exportar_zip(self):
        nome_sugerido = f"{sanitizar_nome_arquivo(self.input_titulo_projeto.text().strip())}_pacote.zip"
        caminho, _ = QFileDialog.getSaveFileName(
            self,
            "Exportar Pacote ZIP Completo",
            str(Path.cwd() / nome_sugerido),
            "Pacote ZIP (*.zip)",
        )
        if caminho:
            try:
                cenas = [c.obter_dados() for c in self.cards_cenas]
                exportar_projeto_zip(
                    caminho_zip=Path(caminho),
                    titulo=self.input_titulo_projeto.text().strip(),
                    config_geral=self.obter_config_geral_dict(),
                    cenas=cenas,
                )
                QMessageBox.information(self, "Sucesso", f"Pacote ZIP exportado com sucesso em:\n{caminho}")
            except Exception as e:
                QMessageBox.critical(self, "Erro", f"Falha ao exportar ZIP:\n{e}")

    def _acao_carregar_json(self):
        caminho, _ = QFileDialog.getOpenFileName(
            self,
            "Carregar Projeto JSON",
            str(Path.cwd()),
            "Arquivos JSON (*.json);;Todos os Arquivos (*)",
        )
        if caminho:
            try:
                self._carregar_projeto_de_arquivo(Path(caminho))
                QMessageBox.information(self, "Sucesso", "Projeto carregado com sucesso!")
            except Exception as e:
                QMessageBox.critical(self, "Erro", f"Falha ao carregar arquivo:\n{e}")

    def _acao_importar_zip(self):
        caminho_zip, _ = QFileDialog.getOpenFileName(
            self,
            "Importar Pacote ZIP",
            str(Path.cwd()),
            "Pacote ZIP (*.zip);;Todos os Arquivos (*)",
        )
        if caminho_zip:
            try:
                pasta_destino = Path("temp_desktop/importados") / f"proj_{int(time.time())}"
                dados = descompactar_e_importar_zip(Path(caminho_zip), pasta_destino)
                self._restaurar_projeto_de_dados(dados)
                QMessageBox.information(self, "Sucesso", "Pacote ZIP importado com sucesso!")
            except Exception as e:
                QMessageBox.critical(self, "Erro", f"Falha ao importar pacote ZIP:\n{e}")

    def _carregar_projeto_de_arquivo(self, caminho: Path):
        dados = carregar_projeto_json(caminho)
        self._restaurar_projeto_de_dados(dados)

    def _restaurar_projeto_de_dados(self, dados: Dict[str, Any]):
        self._limpar_todas_cenas()

        titulo = dados.get("titulo_tutorial") or dados.get("titulo", "Meu Vídeo Tutorial")
        self.input_titulo_projeto.setText(titulo)

        cfg = dados.get("configuracoes_gerais") or dados.get("configuracoes", {})
        voz = cfg.get("voz_padrao") or cfg.get("voz")
        if voz:
            idx = self.combo_voz_padrao.findData(voz)
            if idx >= 0:
                self.combo_voz_padrao.setCurrentIndex(idx)

        taxa = cfg.get("taxa_fala_padrao") or cfg.get("taxa_fala")
        if taxa:
            self.combo_taxa_padrao.setCurrentText(taxa)

        res = cfg.get("resolucao_padrao")
        if res and isinstance(res, (list, tuple)) and len(res) == 2:
            tpl = (int(res[0]), int(res[1]))
            idx = self.combo_resolucao.findData(tpl)
            if idx >= 0:
                self.combo_resolucao.setCurrentIndex(idx)

        pausa = cfg.get("pausa_final_padrao") or cfg.get("pausa_final_cena")
        if pausa is not None:
            self.spin_pausa.setValue(float(pausa))

        cenas_raw = dados.get("cenas") or dados.get("passos", [])
        if cenas_raw:
            for c_raw in cenas_raw:
                self._adicionar_nova_cena(c_raw)
        else:
            self._adicionar_nova_cena()

    def _acao_limpar_temporarios(self):
        removidos = limpar_arquivos_temporarios(Path("temp_desktop"))
        QMessageBox.information(self, "Limpeza Concluída", f"Cache limpo com sucesso! ({removidos} diretórios removidos)")

    # ==========================================================================
    # Pipeline de Renderização e Execução
    # ==========================================================================

    def _iniciar_geracao_video(self):
        cenas_dados = [c.obter_dados() for c in self.cards_cenas]

        # Validações prévias
        erros = []
        for c in cenas_dados:
            if not c["caminho_midia"] or not Path(c["caminho_midia"]).is_file():
                erros.append(f"Cena {c['numero']:02d}: Selecione uma gravação ou captura de tela válida.")
            if not c["texto_narracao"] and not c["legenda"]:
                erros.append(f"Cena {c['numero']:02d}: Digite um texto para a narração ou legenda.")

        if erros:
            msg = "\n".join(erros[:5])
            if len(erros) > 5:
                msg += f"\n... e mais {len(erros)-5} erros."
            QMessageBox.warning(self, "Pendências de Configuração", f"Corrija os seguintes itens antes de gerar:\n\n{msg}")
            return

        # Prepara a UI para o estado de processamento
        self.btn_gerar.setEnabled(False)
        self.btn_cancelar.setEnabled(True)
        self.painel_resultado.setVisible(False)
        self.progress_bar.setValue(0)
        self.log_console.clear()
        self.lbl_status.setText("Iniciando geração do vídeo...")

        # Inicia a Worker Thread
        self.thread_renderizacao = RenderWorkerThread(
            titulo_projeto=self.input_titulo_projeto.text().strip(),
            config_geral=self.obter_config_geral_dict(),
            cenas=cenas_dados,
            parent=self,
        )

        self.thread_renderizacao.progresso.connect(self._atualizar_progresso)
        self.thread_renderizacao.log_msg.connect(self._adicionar_log)
        self.thread_renderizacao.concluido.connect(self._renderizacao_concluida)
        self.thread_renderizacao.falhou.connect(self._renderizacao_falhou)
        self.thread_renderizacao.start()

    def _cancelar_geracao_video(self):
        if self.thread_renderizacao and self.thread_renderizacao.isRunning():
            self.thread_renderizacao.cancelar()
            self.btn_cancelar.setEnabled(False)
            self.lbl_status.setText("Cancelando renderização...")

    def _atualizar_progresso(self, pct: int, msg: str):
        self.progress_bar.setValue(pct)
        self.lbl_status.setText(msg)

    def _adicionar_log(self, msg: str, nivel: str):
        cores = {
            "info": "#93c5fd",
            "sucesso": "#34d399",
            "alerta": "#fde047",
            "erro": "#f87171",
        }
        cor = cores.get(nivel, "#e2e8f0")
        hora = time.strftime("%H:%M:%S")
        html = f"<span style='color:#64748b;'>[{hora}]</span> <span style='color:{cor};'>{msg}</span>"
        self.log_console.append(html)
        # Scroll automático para a última linha
        scrollbar = self.log_console.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())

    def _renderizacao_concluida(self, caminho_video: str, duracao: float):
        self.btn_gerar.setEnabled(True)
        self.btn_cancelar.setEnabled(False)
        self.ultimo_video_gerado = caminho_video

        tamanho_mb = Path(caminho_video).stat().st_size / (1024 * 1024)
        minutos = int(duracao // 60)
        segundos = int(duracao % 60)

        self.lbl_resultado_info.setText(
            f"🎉 Vídeo gerado com sucesso!\n"
            f"Duração: {minutos}m {segundos:02d}s ({duracao:.1f}s) | Tamanho: {tamanho_mb:.1f} MB | Arquivo: {Path(caminho_video).name}"
        )
        self.painel_resultado.setVisible(True)

    def _renderizacao_falhou(self, erro: str):
        self.btn_gerar.setEnabled(True)
        self.btn_cancelar.setEnabled(False)
        self.lbl_status.setText("Falha na geração do vídeo.")
        QMessageBox.critical(self, "Erro na Renderização", f"Ocorreu um erro durante o processamento:\n{erro}")

    def _abrir_video_gerado(self):
        if self.ultimo_video_gerado and Path(self.ultimo_video_gerado).is_file():
            abrir_arquivo_no_sistema(self.ultimo_video_gerado)

    def _abrir_pasta_saida(self):
        if self.ultimo_video_gerado:
            abrir_pasta_no_sistema(str(Path(self.ultimo_video_gerado).parent))
        else:
            abrir_pasta_no_sistema("saida")

    def _salvar_copia_video(self):
        if not self.ultimo_video_gerado or not Path(self.ultimo_video_gerado).is_file():
            return
        origem = Path(self.ultimo_video_gerado)
        destino, _ = QFileDialog.getSaveFileName(
            self,
            "Salvar Cópia do Vídeo",
            str(Path.home() / origem.name),
            "Vídeo MP4 (*.mp4);;Todos os Arquivos (*)",
        )
        if destino:
            try:
                shutil.copyfile(origem, destino)
                QMessageBox.information(self, "Sucesso", f"Cópia salva com sucesso em:\n{destino}")
            except Exception as e:
                QMessageBox.critical(self, "Erro", f"Falha ao salvar cópia:\n{e}")

    def closeEvent(self, event):
        """Garante encerramento seguro de threads de renderização ao fechar o aplicativo."""
        if self.thread_renderizacao and self.thread_renderizacao.isRunning():
            self.thread_renderizacao.cancelar()
            self.thread_renderizacao.wait(2000)
        event.accept()



# ==============================================================================
# Funções Auxiliares de Integração com o SO (Linux / Windows)
# ==============================================================================

def abrir_arquivo_no_sistema(caminho: str):
    """Abre um arquivo no visualizador/player padrão do sistema operacional."""
    caminho_abs = str(Path(caminho).resolve())
    sistema = platform.system()
    try:
        if sistema == "Windows":
            os.startfile(caminho_abs)
        elif sistema == "Darwin":
            subprocess.run(["open", caminho_abs], check=False)
        else:
            subprocess.run(["xdg-open", caminho_abs], check=False)
    except Exception as e:
        print(f"Erro ao abrir arquivo no sistema: {e}")


def abrir_pasta_no_sistema(caminho_pasta: str):
    """Abre o diretório no gerenciador de arquivos nativo do SO."""
    pasta_abs = str(Path(caminho_pasta).resolve())
    sistema = platform.system()
    try:
        if sistema == "Windows":
            os.startfile(pasta_abs)
        elif sistema == "Darwin":
            subprocess.run(["open", pasta_abs], check=False)
        else:
            subprocess.run(["xdg-open", pasta_abs], check=False)
    except Exception as e:
        print(f"Erro ao abrir pasta no sistema: {e}")


# ==============================================================================
# Ponto de Entrada da Aplicação Desktop
# ==============================================================================

def main():
    # Habilita suporte a High DPI em monitores modernos
    os.environ["QT_ENABLE_HIGHDPI_SCALING"] = "1"
    os.environ["QT_AUTO_SCREEN_SCALE_FACTOR"] = "1"

    app = QApplication(sys.argv)
    app.setApplicationName("Gerador de Vídeos Tutoriais IA")
    app.setOrganizationName("VideoAutomate")

    janela = MainWindow()
    janela.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
