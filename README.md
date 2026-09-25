# INOVAPRO SYSTEMS — InovaPro-AIStudio

Repositório operacional de **integração e empacotamento da linha mobile Expo/React Native + backend** da INOVAPRO SYSTEMS.

> **Conectando você ao mundo.**

Princípios oficiais:

- **Entender primeiro. Vender depois.**
- **Problema primeiro. Tecnologia depois. Resultado sempre.**

## Papel deste repositório

Este repositório **não é a aplicação web oficial** e **não é o projeto Android nativo em Kotlin/Jetpack Compose**.

Seu papel atual é operacional:

- armazenar o bundle mobile empacotado;
- reconstruir a fonte mobile em CI;
- executar testes unitários;
- gerar o projeto Android via Expo prebuild;
- compilar APK;
- empacotar a fonte mobile e o backend operacional;
- manter auxiliares de deploy/execução em Railway.

## Fonte canônica por plataforma

- **Web:** `InovaPro.app`
- **Android nativo / Google AI Studio:** `InovaPro-AIStudio-Google`
- **Expo/React Native + empacotamento:** este repositório

## Estrutura observada

- `mobile_bundle.b64` — bundle compactado da fonte mobile
- `railway/` — artefatos e auxiliares do backend/deploy
- `.github/workflows/build-android-apk.yml` — reconstrução e build do APK
- `.github/workflows/package-current-source.yml` — pacote consolidado da fonte atual

## Identidade oficial

- **Empresa:** INOVAPRO SYSTEMS
- **Aplicação:** InovaPro.app
- **Assistente oficial:** Nova AI
- **Slogan:** Conectando você ao mundo.

## Governança

Não duplicar aqui mudanças que pertençam à aplicação web ou ao Android nativo.
Antes de alterar comportamento de produto, confirme qual repositório é a fonte canônica daquela plataforma.

Segredos, tokens privados e credenciais administrativas nunca devem ser versionados.
