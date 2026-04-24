# Regras dos Agentes e Comunicação P2P (Smart Home)

Este documento descreve as regras ativas dos agentes e o protocolo real de comunicação P2P com negociação de potência e load shedding.

---

## 1. Escala de Prioridade

A prioridade segue escala numérica direta: quanto maior o número, maior a prioridade.

- `5`: prioridade máxima (crítico)
- `3-4`: alta
- `2`: média
- `0-1`: baixa

Em conflitos de potência, dispositivos com prioridade numérica menor podem ser forçados a ceder carga para dispositivos mais prioritários.

---

## 2. Regras dos Agentes

### 2.1. Ar Condicionado (AirConditioner)

- **Papel:** conforto térmico do ambiente.
- **Consumo:** ativo `1.35 kW` | idle `0.08 kW`.
- **Regras de atuação:**
  - `AC On - Too Hot`: liga quando `temperatura > target + margem`.
  - `AC Off - Cool Enough`: desliga quando `temperatura < target - margem`.
- **Prioridade:** dinâmica, baseada no desvio absoluto em relação ao alvo (`|temp_atual - target|`):
  - `>= 8°C` -> prioridade `5`
  - `>= 6°C` -> prioridade `4`
  - `>= 4°C` -> prioridade `3`
  - `>= 2°C` -> prioridade `2`
  - `< 2°C` -> prioridade `1`
  - sem leitura de temperatura -> prioridade `3`

### 2.2. Geladeira (Refrigerator)

- **Papel:** manter conservação dos alimentos.
- **Consumo:** compressor ativo `0.18 kW` | idle `0.03 kW`.
- **Regras de atuação:**
  - `Compressor On - Warming Up`: liga quando `temperatura_interna > target + margem`.
  - `Compressor Off - Cool Enough`: desliga quando `temperatura_interna < target - margem`.
- **Prioridade:** fixa em `5` (sempre máxima).

### 2.3 Máquina de Lavar (WashingMachine)

- **Papel:** lavar roupas.
- **Consumo:** ativo `0.5 kW` | idle `0.05 kW`.
- **Regras de atuação:**
  - `Start Washing - numero de roupas > 0`: liga quando há roupas para lavar.
  - O número de roupas pendentes aumenta com o tempo quando a máquina está parada.
- **Prioridade:** dinâmica e crescente com o acúmulo de roupa (quanto mais roupa acumulada, mais urgente lavar e maior o valor numérico da prioridade).
  - pouca roupa -> prioridade baixa (`0-1`)
  - roupa moderada -> prioridade média (`2-3`)
  - muita roupa acumulada -> prioridade alta (`4`)
  - carga crítica/acúmulo prolongado -> prioridade muito alta (`5`)

## 3. Comunicação P2P Correta (Implementada)

Quando um dispositivo precisa ligar e existe configuração com peers, a ligação passa por negociação distribuída.

### 3.1. Broadcast Contínuo de Estado de Potência

Cada agente envia periodicamente para os peers um `power_status` com:

- `device_name`
- `power_kw` atual
- `timestamp`

Esses dados alimentam a estimativa local de consumo total (`peer_power_status`).

### 3.2. Fase de Pedido (`power_request`)

Ao disparar uma regra de `on` com peers ativos:

1. O agente cria um `transaction_id`.
2. Calcula potência projetada ao ligar (`projected_total_kw`).
3. Envia `power_request` para todos os peers contendo:
   - `transaction_id`
   - `requester`
   - `priority` do solicitante
   - `power_needed_kw`
   - `projected_total_kw`
   - `max_power_kw`

### 3.3. Fase de Resposta (`power_reply`)

Cada peer decide localmente:

- `should_shed = True` quando:
  - `projected_total_kw > max_power_kw`, e
  - o peer está acima do consumo idle, e
  - `my_priority < requester_priority` (peer menos prioritário)

- `decision = accept` quando:
  - está dentro do limite (`projected_total_kw <= max_power_kw`), ou
  - consegue ceder carga (`should_shed = True`)

- `decision = reject` quando está acima do limite e não pode ceder.

Cada reply inclui `decision`, `should_shed`, `reason` e `transaction_id`.

### 3.4. Fecho da Negociação (`power_commit` ou `power_abort`)

O solicitante fecha a transação quando:

- recebe todas as respostas esperadas, ou
- ocorre timeout de negociação.

Regra de fecho:

- **COMMIT**: existe pelo menos uma resposta `accept` e:
  - se `projected_total_kw <= max_power_kw`, não precisa shedding adicional; ou
  - se excede o limite, existe um conjunto de peers aceitos cujo shedding cobre o excesso, escolhendo primeiro o menor número de dispositivos possível; em empate, prefere o conjunto com prioridades mais baixas.
- **ABORT**: sem `accept`, timeout sem capacidade suficiente, ou capacidade de shedding aceita insuficiente.

No **COMMIT**, o solicitante liga o atuador e notifica o mundo com `state_changed = ON`.
No **ABORT**, a regra de `on` é liberada para tentar novamente em ciclo futuro.

### 3.5. Load Shedding após COMMIT

Peers que foram selecionados explicitamente pelo solicitante (lista `shed_peers`) aplicam shedding ao receber `power_commit`:

- definem `shed_timeout = 3` ciclos
- executam regras de `off`
- bloqueiam religamento imediato durante penalidade
- notificam o mundo como `OFF (SHED)`

---

## 4. Comportamento de Segurança e Timeout

- Existe comportamento periódico para abortar negociações expiradas.
- Se um agente está em penalidade de shedding (`shed_timeout > 0`), uma regra `on` não é executada.

---

## 5. Resumo Operacional

- A geladeira permanece estruturalmente prioritária (`5`).
- O ar condicionado adapta prioridade conforme desconforto térmico.
- A máquina de lavar eleva prioridade conforme o tempo passa e a roupa acumula.
- A decisão de ligar em modo distribuído depende de consenso P2P contínuo.
- Em sobrecarga, dispositivos menos prioritários cedem carga quando possível.
