from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
from django.utils.translation import gettext as _

from .calha_core import calcular_modelo
from .forms import DEFAULT_ENTRADAS, SimulacaoCalhaForm
from .presentation import montar_apresentacao


SESSION_KEY = "ultimas_entradas_calha"


@login_required
def simuladores(request):
    if request.method == "GET" and request.GET.get("reset") == "padrao":
        request.session.pop(SESSION_KEY, None)
        messages.info(request, _("Entradas restauradas para o padrão de fábrica."))
        return redirect("simulador_calha:home")

    if request.method == "POST":
        form = SimulacaoCalhaForm(request.POST)
        if form.is_valid():
            try:
                dados = form.dados_motor()
                resultado_motor = calcular_modelo(dados)
                apresentacao = montar_apresentacao(dados, resultado_motor)
                request.session[SESSION_KEY] = {
                    name: form.cleaned_data.get(name) for name in form.fields
                }
                return render(request, "simulador_calha/resultado.html", apresentacao)
            except (ValueError, ArithmeticError, OverflowError) as exc:
                messages.error(request, _(str(exc)))
    else:
        form = SimulacaoCalhaForm(initial=request.session.get(SESSION_KEY, DEFAULT_ENTRADAS))

    return render(request, "simulador_calha/formulario.html", {"form": form})
