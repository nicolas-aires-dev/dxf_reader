# 🧪TEST_CASE_1

Para iniciar, foi usar MATCHPROP de um objeto padronizado, que foi espelhado ao perfil que foi testado.

Teste feito com arquivo DXF com um objeto "REGIAO", onde foi utilizado a função "BO" para gerar polilinhas acima dos objetos "REGIAO".

Afim de economizar tempo, o primeiro teste foi feito com os 2 objetos um acima do outro. Como o DxfReader tende a ler apenas Polilinha, Simplenote e Dimensions, supus que funcionaria.

Ao executar o processamento, resultou em: 

## ❌ FALHA
``` 
Traceback (most recent call last):
  File "c:\Users\nicolas.santos\OneDrive - Alumisoft Instalações Ltda\Área de Trabalho\WORKSPACE\WORKSPACE-TOTAL\dxf_reader\main.py", line 287, in <module>
    main()
    ~~~~^^
  File "c:\Users\nicolas.santos\OneDrive - Alumisoft Instalações Ltda\Área de Trabalho\WORKSPACE\WORKSPACE-TOTAL\dxf_reader\main.py", line 281, in main
    render_imagens(doc, perfil, f"{nome_base}")
    ~~~~~~~~~~~~~~^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
```

Ocasionando em outros erros por falta de argumentos.


# 🧪TEST_CASE_2

Ao notar que o primeiro erro vem da função de renderizar a imagem, que recebe 'doc', 'perfil' e (f'{nome_base}'), testei rodar o processamento em outro objeto (O objeto padrão). O objeto foi renderizado com sucesso, então procurei encontrar a diferença entre um objeto e outro.
As diferenças eram claras:
    * Objeto teste continha um objeto 'REGIAO' sobreposto por um objeto 'POLILINHA';
    * Objeto teste tinha o texto como 'NOTA' com quebras de linha, que não são suportados atualmente no processamento.

Como o objetivo era confirmar se os objetos sobrepostos não iriam resultar em erros, apenas troquei o texto do objeto teste, que era do tipo 'Nota' para um texto do tipo 'Simplenote'.

O resultado foi positivo, e o processamento ocorreu como esperado.

# 📌CONCLUSOES

* Os objetos padrões devem ter os textos no tipo 'Simplenote';
* Os objetos 'REGIAO', se sobrepostos por objetos 'POLILINHA', serão ignorados.

# 💡SOLUÇÃO

* Adicionada uma nova utilidade chamada "sanitize_filename", que usa regex para retirar quebras de linha e caracteres especiais e substitui por "_";
* Atualizada a função "extrair_nome", que ignora informação de peso do objeto, se a informação existir. Deixando apenas o código do objeto.




