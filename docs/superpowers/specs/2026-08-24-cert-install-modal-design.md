# Modal de instalação do certificado CA

## Problema

`index.html` já tem um banner ("Primeira vez nesse celular?") oferecendo o download do certificado raiz do mkcert, necessário pra o navegador do celular confiar no HTTPS da Pi. Dois problemas:

1. O link (`href="certs/rootCA.pem"`) está quebrado — o arquivo nunca foi colocado em `server/static/certs/`.
2. O botão "Já instalei, não mostrar de novo" descarta o aviso permanentemente no primeiro clique, mesmo que a pessoa não tenha realmente instalado — fácil de perder a oportunidade e só descobrir o bloqueio depois, na hora de gravar.

## Escopo

Só a Home (`index.html`). Não mexe em `cameras.html`/`capture.html` nem nas outras páginas.

## Comportamento

Substituir o banner por um **modal bloqueante**, aberto automaticamente ao carregar a Home enquanto o certificado não estiver confirmado como instalado:

- Overlay cobrindo a tela, card centralizado, reaproveitando o conteúdo do banner atual (texto de aviso, botão de download, passo a passo Android de instalação).
- Botão primário **"Baixar certificado"** — dispara o download (`<a download>` para `certs/rootCA.pem`); não fecha o modal.
- Botão secundário **"Já instalei"** — único jeito de fechar o modal. Grava `localStorage.managerreplay_cert_installed = "1"`.
- Sem botão de fechar/X e sem clique-fora-fecha — a única saída é confirmar instalação.
- Se a pessoa sair sem confirmar (fecha aba, navega direto pra outra página por URL), o modal reaparece na próxima vez que a Home carregar, porque a flag no `localStorage` não foi setada.
- Resto da Home fica inacessível por trás do overlay (`overflow: hidden` no body, conteúdo da Home sem `aria-hidden`/focus enquanto modal aberto) até a confirmação.
- Chave de storage muda de `managerreplay_cert_dismissed` (comportamento antigo, dispensa sem confirmar) pra `managerreplay_cert_installed` (só true após confirmação real) — nomeação nova reflete a semântica nova.

## Correção do arquivo do certificado

O `rootCA.pem` do mkcert não está em `server/static/certs/`. Local do arquivo original (mkcert usa um CA root por máquina, gerado uma vez):

```bash
mkcert -CAROOT
# normalmente algo como /home/rocha/.local/share/mkcert/rootCA.pem
```

Copiar pra dentro do static do app, no Pi:

```bash
mkdir -p ~/managerreplay/server/static/certs
cp "$(mkcert -CAROOT)/rootCA.pem" ~/managerreplay/server/static/certs/rootCA.pem
```

Esse passo é manual, executado uma vez no Pi (não faz parte do código do repo — o arquivo do CA é específico da máquina que gerou o certificado, não deve ser versionado).

## Testes / verificação

Sem suite automatizada de UI neste projeto (é HTML/JS estático). Verificação manual:
- Abrir `index.html` sem a flag no `localStorage` → modal aparece, resto da página bloqueado.
- Clicar "Baixar certificado" → download inicia, modal continua aberto.
- Clicar "Já instalei" → modal fecha, `localStorage` setado, recarregar a página → modal não aparece mais.
- Limpar `localStorage` → modal volta a aparecer.
