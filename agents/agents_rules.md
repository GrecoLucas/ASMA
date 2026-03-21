# Regras dos Agentes e Comunicação P2P (Smart Home)

Este documento centraliza as regras embasadas em cada agente operante do sistema e detalha a arquitetura de **Comunicação P2P e Load Shedding (Deslastre de Carga)** baseada em prioridades que rege a harmonia da casa inteligente.

---


## 2. Visão Geral dos Nossos Agentes em Regra

As prioridades acompanham um ranqueamento numérico invertido. **Números pequenos reinam impunemente sobre os pares paralelos de números maiores.**

### 2.1. O Ar Condicionado (Air Conditioner)
- **Papel:** Refrigeração ambiental focada totalmente na manutenção confortável do clima interior.
- **Prioridade:** `5` (Mínima, perante a geladeira). A climatização cede sob pressão a aparelhos estruturais aquando de possíveis conflitos estipulados de P2P.
- **Consumo Padrão:** Em Ativo (`1.35 kW`) | Em Inativo/Idle (`0.08 kW`).
- **Árvore de Regras (`rules`):**
  - **`AC On - Too Hot`**: Se o sensor térmico do ambiente ditar uma temperatura acima de `Target + Margem` *(ex: Alvo de 22°C + Margem de 2°C = Acima de 24°C)*, ativa o protocolo de inicialização e liga-se.
  - **`AC Off - Cool Enough`**: Se a temperatura real baixar perante o valor de `Target - Margem` *(ex: Abaixo dos 20°C)*, revoga o ciclo fechando os compressores frios da unidade residencial.

### 2.2. A Geladeira Inteligente (Refrigerator)
- **Papel:** Congelamento contínuo inabalável em nome da longevidade alimentar no lar.
- **Prioridade:** `1` (A Prioridade Suprema Imbatível). Este equipamento passa sempre perfeitamente isento a um *Shedding* indesejado face a um Ar Condicionado.
- **Consumo Padrão:** Em Ativo (`0.18 kW`) | Em Inativo/Idle (`0.03 kW`).
- **Árvore de Regras (`rules`):**
  - **`Compressor On - Warming Up`**: Se os simuladores registarem um aquecimento da cápsula interior (*> Target + Margem*, como por exemplo acima dos 5°C), a geladeira liga o motor de compressão.
  - **`Compressor Off - Cool Enough`**: Uma vez batido o arrefecimento sub-limite em *(-)* (abaixo de 3°C), os compressores pausam para o patamar de *IDLE* ou *Stand By*.
