#!/usr/bin/env python3
"""
gerar_tutorial.py
=================
Ponto de entrada de conveniência que redireciona para o motor modular 'gerador_generico.py'.
Mantém total compatibilidade com chamadas anteriores.
"""

import sys
from pathlib import Path
from gerador_generico import main

if __name__ == "__main__":
    # Executa o fluxo padrão com config_projeto.json
    main()

