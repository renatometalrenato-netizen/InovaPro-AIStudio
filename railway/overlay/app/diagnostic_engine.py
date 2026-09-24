"""Pure deterministic engine for the InovaPro 360° diagnostic.

No database or framework dependencies: safe to unit-test in isolation.
"""
from typing import Dict, List, Literal

PILLARS = [
    {"id": "estrategia", "name": "Estratégia", "description": "Clareza de objetivos, prioridades e direção do negócio."},
    {"id": "posicionamento", "name": "Posicionamento & Marca", "description": "Proposta de valor, diferenciação e percepção da marca."},
    {"id": "marketing", "name": "Marketing & Conteúdo", "description": "Aquisição, presença digital e consistência de comunicação."},
    {"id": "vendas", "name": "Vendas & CRM", "description": "Processo comercial, acompanhamento e conversão de oportunidades."},
    {"id": "processos", "name": "Processos & Operação", "description": "Padronização, produtividade e organização da execução."},
    {"id": "tecnologia", "name": "Tecnologia & Automação", "description": "Uso de ferramentas, integrações e automação com propósito."},
    {"id": "gestao", "name": "Dados & Gestão", "description": "Indicadores, tomada de decisão e ritmo de acompanhamento."},
]

QUESTIONS = [
    {"id": "q01", "pillar": "estrategia", "text": "Seu negócio tem metas claras para os próximos 90 dias?"},
    {"id": "q02", "pillar": "estrategia", "text": "Você sabe quais produtos, serviços ou ofertas devem receber prioridade agora?"},
    {"id": "q03", "pillar": "estrategia", "text": "As principais decisões do negócio seguem um plano, e não apenas urgências do dia a dia?"},
    {"id": "q04", "pillar": "posicionamento", "text": "Você consegue explicar em poucas frases por que um cliente deveria escolher sua empresa?"},
    {"id": "q05", "pillar": "posicionamento", "text": "Sua identidade visual e sua comunicação são consistentes nos canais onde a empresa aparece?"},
    {"id": "q06", "pillar": "posicionamento", "text": "Seu público-alvo está definido de forma prática, com dores, necessidades e perfil de compra conhecidos?"},
    {"id": "q07", "pillar": "marketing", "text": "Sua empresa produz conteúdo ou campanhas com frequência planejada?"},
    {"id": "q08", "pillar": "marketing", "text": "Você consegue identificar quais canais realmente geram contatos, leads ou vendas?"},
    {"id": "q09", "pillar": "marketing", "text": "Existe uma chamada para ação clara levando o público para o próximo passo?"},
    {"id": "q10", "pillar": "vendas", "text": "Existe um processo definido desde o primeiro contato até o fechamento e pós-venda?"},
    {"id": "q11", "pillar": "vendas", "text": "Leads e oportunidades são registrados e acompanhados sem depender apenas da memória ou do WhatsApp?"},
    {"id": "q12", "pillar": "vendas", "text": "Sua equipe ou você faz follow-up com frequência e critérios definidos?"},
    {"id": "q13", "pillar": "processos", "text": "As tarefas recorrentes mais importantes possuem um padrão ou passo a passo claro?"},
    {"id": "q14", "pillar": "processos", "text": "Você consegue identificar rapidamente gargalos, atrasos e retrabalho na operação?"},
    {"id": "q15", "pillar": "processos", "text": "As responsabilidades estão claras para quem executa cada atividade do negócio?"},
    {"id": "q16", "pillar": "tecnologia", "text": "As ferramentas usadas hoje conversam entre si ou evitam trabalho manual repetitivo?"},
    {"id": "q17", "pillar": "tecnologia", "text": "Seu negócio já automatiza tarefas como atendimento, captação, follow-up, cadastro ou relatórios?"},
    {"id": "q18", "pillar": "tecnologia", "text": "Você escolhe tecnologia a partir de um problema real e de um resultado esperado?"},
    {"id": "q19", "pillar": "gestao", "text": "Você acompanha indicadores essenciais de vendas, marketing, operação ou caixa com frequência?"},
    {"id": "q20", "pillar": "gestao", "text": "As decisões importantes usam dados registrados, e não apenas percepção ou improviso?"},
    {"id": "q21", "pillar": "gestao", "text": "Existe uma rotina de revisão de resultados e definição das próximas ações?"},
]

ANSWER_OPTIONS = [
    {"value": 1, "label": "Não acontece"},
    {"value": 2, "label": "Acontece raramente"},
    {"value": 3, "label": "Acontece às vezes"},
    {"value": 4, "label": "Acontece com frequência"},
    {"value": 5, "label": "É consistente e medido"},
]

PILLAR_RECOMMENDATIONS = {
    "estrategia": {"low": "Defina uma meta principal de 90 dias, até três prioridades e um responsável por cada próxima ação.", "mid": "Transforme objetivos em metas mensuráveis e revise prioridades semanalmente para reduzir dispersão.", "high": "Conecte metas, orçamento e capacidade operacional para acelerar crescimento sem perder foco."},
    "posicionamento": {"low": "Clarifique público, dor principal, promessa e diferenciais; depois padronize a comunicação da marca.", "mid": "Teste mensagens e ofertas por segmento e fortaleça provas, diferenciais e consistência visual.", "high": "Aprofunde segmentação, autoridade e arquitetura de ofertas para defender margem e percepção de valor."},
    "marketing": {"low": "Escolha poucos canais prioritários, crie calendário simples e use uma chamada para ação mensurável.", "mid": "Acompanhe origem dos leads e otimize conteúdo e campanhas com base em custo, qualidade e conversão.", "high": "Escale os canais comprovados com testes controlados, remarketing e conteúdo orientado por dados."},
    "vendas": {"low": "Crie etapas comerciais simples, registre todos os leads e adote uma rotina básica de follow-up.", "mid": "Padronize qualificação, proposta, objeções e cadência de follow-up dentro do CRM.", "high": "Otimize conversão por etapa, tempo de ciclo, ticket e motivos de ganho ou perda."},
    "processos": {"low": "Mapeie as tarefas recorrentes críticas e documente o passo a passo mínimo para reduzir retrabalho.", "mid": "Defina responsáveis, prazos e pontos de controle; elimine gargalos antes de automatizar.", "high": "Monitore capacidade, qualidade e tempo de ciclo para escalar a operação com previsibilidade."},
    "tecnologia": {"low": "Liste trabalhos manuais repetitivos e priorize uma automação pequena ligada a ganho claro de tempo ou receita.", "mid": "Integre ferramentas e automatize fluxos com regras, logs e possibilidade de intervenção humana.", "high": "Evolua para automações conectadas, IA assistiva e governança de dados com métricas de retorno."},
    "gestao": {"low": "Escolha poucos indicadores essenciais e faça uma revisão semanal com decisões e responsáveis definidos.", "mid": "Centralize indicadores e compare resultado realizado versus meta para orientar prioridades.", "high": "Use tendências, coortes e previsões simples para antecipar gargalos e alocação de recursos."},
}

def maturity_level(score: int) -> Literal["Fundação", "Estruturação", "Crescimento", "Escala"]:
    if score < 40: return "Fundação"
    if score < 60: return "Estruturação"
    if score < 80: return "Crescimento"
    return "Escala"

def _band(score: int) -> str:
    if score < 50: return "low"
    if score < 75: return "mid"
    return "high"

def calculate_result(answers: Dict[str, int]) -> dict:
    grouped: Dict[str, List[int]] = {pillar["id"]: [] for pillar in PILLARS}
    for question in QUESTIONS:
        grouped[question["pillar"]].append(answers[question["id"]])
    pillar_scores = {p["id"]: round((sum(grouped[p["id"]]) / len(grouped[p["id"]])) * 20) for p in PILLARS}
    overall_score = round(sum(pillar_scores.values()) / len(pillar_scores))
    ordered = sorted(pillar_scores.items(), key=lambda item: (-item[1], item[0]))
    strengths = [pillar_id for pillar_id, _ in ordered[:2]]
    priorities = [pillar_id for pillar_id, _ in sorted(pillar_scores.items(), key=lambda item: (item[1], item[0]))[:3]]
    recommendations = [{"pillar": pillar_id, "text": PILLAR_RECOMMENDATIONS[pillar_id][_band(pillar_scores[pillar_id])]} for pillar_id in priorities]
    return {"overall_score": overall_score, "level": maturity_level(overall_score), "pillar_scores": pillar_scores, "strengths": strengths, "priorities": priorities, "recommendations": recommendations}

SMART_QUESTIONS = [
    {"id": "s01", "pillar": "estrategia", "text": "Você tem uma meta principal e até três prioridades claras para os próximos 90 dias?"},
    {"id": "s02", "pillar": "posicionamento", "text": "Seu cliente entende rapidamente o que você vende, para quem e por que escolher sua empresa?"},
    {"id": "s03", "pillar": "marketing", "text": "Você sabe quais canais realmente geram contatos, oportunidades ou vendas?"},
    {"id": "s04", "pillar": "vendas", "text": "Existe um processo organizado do primeiro contato até follow-up, proposta e fechamento?"},
    {"id": "s05", "pillar": "processos", "text": "As tarefas recorrentes importantes seguem um padrão claro, sem depender só da memória?"},
    {"id": "s06", "pillar": "tecnologia", "text": "Seu negócio já usa integrações ou automações para reduzir trabalho manual repetitivo?"},
    {"id": "s07", "pillar": "gestao", "text": "Você acompanha poucos indicadores essenciais e revisa resultados com frequência?"},
]

def calculate_smart_result(answers: Dict[str, int]) -> dict:
    question_by_pillar = {q["pillar"]: q for q in SMART_QUESTIONS}
    pillar_scores = {p["id"]: answers[question_by_pillar[p["id"]]["id"]] * 20 for p in PILLARS}
    overall_score = round(sum(pillar_scores.values()) / len(pillar_scores))
    ordered = sorted(pillar_scores.items(), key=lambda item: (-item[1], item[0]))
    strengths = [pillar_id for pillar_id, _ in ordered[:2]]
    priorities = [pillar_id for pillar_id, _ in sorted(pillar_scores.items(), key=lambda item: (item[1], item[0]))[:3]]
    recommendations = [{"pillar": pillar_id, "text": PILLAR_RECOMMENDATIONS[pillar_id][_band(pillar_scores[pillar_id])]} for pillar_id in priorities]
    return {"overall_score": overall_score, "level": maturity_level(overall_score), "pillar_scores": pillar_scores, "strengths": strengths, "priorities": priorities, "recommendations": recommendations}
