# Simulador Geral Django

Aplicação web Django para executar o motor de cálculo do simulador de transporte de polpas.

## Estrutura

- `Simuladormodelo/codigo/calculos.py`: funções numéricas extraídas do simulador Python original e função pura `executar_simulacao`.
- `Simuladormodelo/forms.py`: formulário Django para entradas do simulador.
- `Simuladormodelo/views.py`: views protegidas por login.
- `templates/`: telas HTML.
- `static/js/graficos.js`: gráficos Plotly no navegador.

## Como rodar

```bash
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

Depois acesse:

```text
http://127.0.0.1:8000/
```

## Observações

O motor de cálculo web não usa Tkinter, não abre janelas e não chama `plt.show()`. Ele retorna dicionários, listas e valores numéricos serializáveis para o Django.

Quando o critério de escoamento homogêneo é atingido, a aplicação informa um aviso e mantém o cálculo heterogêneo por padrão. A seleção interativa do modelo homogêneo da versão local era dependente de janela Tkinter e deve virar um campo web em uma próxima evolução.