# 2do Proyecto de Compilación: Cool Compiler

> * Rodrigo Daniel Pino Trueba
> * Aldo Verdesia Delgado
> * C312

## Ejecución el Proyecto

### Requisitos

La interfaz visual del proyecto se apoya en las bibliotecas de Streamlit, y estas a su vez se apoyan en Anaconda y Python 3.7. Fuera de estas no existe otra dependencia necesaria.

---

### Manual

Luego de tener instalados los requisitos ejecutar en la consola, en la raíz del proyecto, el comando:

```bash
streamlit run zApp.py
```

Debe abrir el browser y dirigirse a la dirección que indique el resultado.

En la página principal se observan las siguientes cosas:

1. El Título...

2. Un cuadro para seleccionar si queremos importar un archivo escrito o escribir el código directamente en la página. Nosotros recomendamos importar por un problema de comodidad, pero usted decide.

3. Si decide escribir en vez de importar, le aparecerá un cuadro de texto que será el input del programa.

4. Si importa se le pide que introduzca la dirección de la CARPETA donde está el archivo que quiere probar, y en el recuadro de abajo le pide que seleccione un archivo a ejecutar.

5. Haciendo click en el botón __submit__ se ejecuta el programa.

En la esquina superior izquierda, hay una flecha que si se da click muestra nuevas opciones. Muchas de estas se explican por si solas:

* Show Parsing, muestra los pasos del parser.

* Show Types Computed da una lista al final de la ejecución de todos los nodos y sus valores.

* Show Scope muestra las variables y sus tipos calculados.

* Show Result muestra la existencia, o no, de los errores y donde ocurrieron.

---

## Estructura del proyecto

El proyecto se basa en la gramática Cool y utiliza un parser LR(1).

El proyecto está estructurado en el siguiente orden:

* Type Collector

* Type Builder

* Inference Gatherer

* Type Inferencer

* Type Linker

* Type Finisher

---

### Type Collector

El Type Collector consiste en la recolección de todos los tipos definidos en el programa. Los tipos por defecto como Object, Int, IO, etc... son añadidos por defecto siempre al inicio del programa.

Además de recolectar tipos, el Type Collector se encarga de crear un árbol conformado por dichos tipos, ordena las clases para que las siguientes búsquedas que utilzan el patrón visitor nunca verifiquen un hijo antes que su padre. También detecta la herencia circular y la señala, pero los tipos que pertenecen a ella no son analizados en las recorridos.

---

### Type Builder

El Type Builder es el que se encarga de inicializar los tipos recolectados definiendo sus métodos y variables. También detecta errores tempranos como si un atributo, función o parámetros se inicializan sin el tipo correctos.

---

### Inference Gatherer

Para la correcta integración del inferenciador se decidió dividir lo que sería el chequeo semántico en cuatro 4 recorridos distintos del patrón visitor, el Inference Gatherer consiste en la primera de estas partes. Como el chequeo semántico esta divido, cada pedazo analiza una porción de las reglas a cumplir.

El Inference Gatherer en su recorrido detecta todos los Auto Types y trata de inferir su valor, como veremos más adelante es el más permisivo de los recorridos visitores implementados.

El método utilizado para inferir Auto Types consiste en tratar cada Auto Type recién encontrado como una bolsa con todos los posibles tipos dentro de él, exceptuando a los Error Types y otro Auto Type. Mientras se va recorriendo el AST se van imponiendo restricciones (siempre que corresponda) sobre la bolsa de tipos, reduciéndola. Cuando se reduce una bolsa de tipos esta nunca vuelve a crecer, incorporar un viejo tipo nuevamente a una bolsa implica un error pués ese tipo se removió explicitamente porque en el recorrido se encontró una condición para la cual no era válido.

Las bolsas al estar compuestas por tipos, y estos a su vez tienen tipos de los que heredan y tipos que heredan de ellos, se pueden ver como un conjunto de árboles. Si en una bolsa hay 2 o más árboles significa que ese Auto Type es ambiguo y no se puede definir correctamente, pues si una bolsa tiene 2 árboles significa que sustituyendo el Auto Type por cualquier miembro de esos árboles no causaría error de ejecución, provocando la duda del compilador sobre por cual tipo de cada árbol sustituir por el Auto Type.

Mencionamos anterioremente que este era el recorrido más permisivo y lo es así porque permite a los Auto Types tener ambiguedad, pues un recorrido a medias sólo no basta para desambiguar una bolsa. Por ejemplo si un Auto Type al principio de la ejecución tiene dos tipos posibles, no lo podemos desestimar ni catalogarlo de error pues puede que más adelante en el código se encuentre la condición que lo desambigue.

El Inference Gatherer los únicos errores que detecta es cuando se necesita de una variable y esta no se ha definido todavía o no existe.

---

### Type Inferencer

El Type Inferencer sigue la misma idea que el Type Gatherer pero con ciertos cambios. En este recorrido ya no se permite ambiguedad en las bolsas de tipo pués si en un recorrido completo no se infirió, en un segundo tampoco se inferirá. Notése que un recorrido completo se analizan todas las restricciones de una bolsa.

El Type Inferencer se realiza una o dos veces dependiendo si se actualizan algun valor inferido. Si en el primer recorrido encuentra errores no realiza un segundo, independiente de si hubo algun cambio o no. En este recorrdio se detectan los errores por ambiguedad.

---

### Type Linker

El Type Linker es la tercera parte del chequeo semántico y donde más estricto se verifican las reglas de Cool.

En este recorrido se analizan todos los tipos posibles de cada nodo del AST, variable definida y retorno de los métodos. A cada nodo se le asigna su valor más estricto posible, si se encuentra alguna restricción, pasa a un valor más general. Notemos que en el caso de la bolsa de tipos pueden haber dos Auto Types "distintos" pero a la vez entrelazados como por ejemplo un parámetro de un método Auto Type T1 que a la vez se pasa a una función cuyo parámetro también es Auto Type T2, en este caso las restricciones sobre T2 influyen sobre T1 y viceversa. El Type Linker mantiene la consistencia entre ambos.

El Type Linker se ejecuta dos veces (una sola si se encuentra un error) para actualizar, en caso de ser necesario, las bolsas que se inicializaron al principio y luego fueron restringidas.

---

### Type Finisher

El Type Finisher es el último recorrido que se realiza sobre el AST, no verifica errores, solo actualiza definitivamente el valor computado de un nodo, basado en su posición. Los parámetros se les actualizará las mas general y a los demás la más estricta (posible). Si un nodo puede ser de varios tipos a la vez se le actualiza al tipo que es unión de todas las ramas. Estas ramas siempre van a encontrar un ancestro común dentro de la bolsa de tipos pués confoman parte del mismo árbol.

---

## Extra

### Detalles de Implementación

1. La comunicación entre los visitores se hace a traves del mismo AST. El Inference Gatherer y el Type Inferecer se apoyan en la propiedad node.inferenced_type donde pueden estar almacenados AutoTypes y Tipos indeferentemente.

2. El Type Linker y el Type Finisher se comunican a través de la propiedad node.computed_type y se apoyan en node.inferenced_type. Durante la ejecución del Type Linker la propiedad node.computed_type es una lista con todos los posibles tipos que puede tener un nodo, ordenados de menor a mayor en generalidad. Dos nodos relacionados pueden compartir la misma lista, excepto en el caso del tipo de retorno de los CallNodes, donde para compatibilidad con los Self Types, se realiza una copia a los nodes relacionados con estos. Esto es una de las razones de porque el Type Linker se ejecuta dos veces, pues si el original o las copias tuvieron algun cambio no se actualizan hasta la segunda pasada.

3. El Scope se crea una vez, al igual que las variables definidas en él. Esto se realiza en el Inference Gatherer. Después todos los demás recorridos se encargan sólo de actualizar los valores de dichas variables. A las variables se le aplican las mismas reglas que a los nodos. Si son bolsas de tipos nunca pueden aumentar la cantidad.

---

### Notas

El proyecto ha sido re-escrito varias veces tratando de lograr el mayor poder de inferencia posible. Al estar divido el proyecto en varias partes, es posible que exista un error o bug inesperado, debido a algun error entre las comunicaciones entre los distintos recorridos, no obstante esto no suele ocurrir en un código correcto, y rara vez pasa en un incorrecto. Cabe decir que cada vez que se detecta un evento de este tipo se arregla.

---

## Ejemplo

Mostremos con un ejemplo el funcionamiento del proyecto:

```python
class Main {
	main(a:AUTO_TYPE, b:AUTO_TYPE) : AUTO_TYPE {
        ackermann(a, b)
    };
	
	ackermann(m : AUTO_TYPE, n: AUTO_TYPE) : AUTO_TYPE {
		if (m=0) then n+1 else
			if (n=0) then ackermann(m-1, 1) else
				ackermann(m-1, ackermann(m, n-1))
			fi         
		fi     
	};
};
```
Primeramente el Type Collector y el Type Builder definiran e inicializaran las clases, parámetro de los métodos y sus valores de retorno. Los Auto Types se instancian en orden decendiente y se les asigna un número de serie.
```python
class Main {
	main(a:T2, b:T3) : T1 {
        ackermann(a, b)
    };
	
	ackermann(m : T5, n: T6) : T4 {
		if (m=0) then n+1 else
			if (n=0) then ackermann(m-1, 1) else
				ackermann(m-1, ackermann(m, n-1))
			fi         
		fi     
	};
};
```
Luego se ejecuta el Inference Gatherer, va inicializar todos los AutoTypes e ir reduciéndolos a medida que encuentre condiciones. Podemos ver que "a" y "b" en el metodo "main" no tienen ningun constrain, así que pueden tomar cualquier valor, su bolsa se mantiene llena. Para "a" y "b" una posible condición podrían ser el tipo de "m" y "n" parámetros de la función de la que ellos son argumentos, pero estas tambien en este momento pueden tener todos los posibles valores.
Para T1 y T4(El valor de retorno del método ackerman), tampoco hay ningun constraint.

En el método "ackerman" los valores "m" y "n" si tienen constraints y su bolsa se puede reducir aun más. El segundo IF, llamémoslo IF2, sus expresiones THEN y ELSE estan compuestas por métodos "ackerman"(T4) que pueden ser todos los posibles tipos, y por tanto este IF2 que es el join entre ellos también puede tener todos los valores posibles.

El IF1 y tiene en su THEN al tipo Int y en su ELSE al IF2, que representa todos los valores posibles. El join enre estos miembros  son los ancestros comunes entre ambos conjuntos. Luego:

>Join(Int, [Object, String, Bool, IO, Main, Int]) = [Int, Object] = IF2

Luego IF1 puede ser del tipo Int o del tipo Object. Además IF1 es el valor de retornon de Ackerman(T4), lo que trae como consecuencia que T4 también pueda ser de los tipos [Int, Object].Luego:

```python
class Main {
	main(a:(ALL), b:(ALL)) : (ALL) {
        ackermann(a, b)
    };
	
	ackermann(m : (Int), n: (Int)) : (Int, Object) {
		if (m=0) then n+1 else
			if (n=0) then ackermann(m-1, 1) else
				ackermann(m-1, ackermann(m, n-1))
			fi         
		fi     
	};
    -- Con IF1 siendo(Int, Obj) e IF2 siendo (ALL).
    -- ALL es una manera corta de referirnos a todos los tipos.
};
```

Luego de una segunda pasada por Type Inferencer aplicando los constraints. En este caso como "a" es todos los posibles tipos pero se pasa como argumento de una función que sólo permite enteros en sus parámetros queda reducido. Lo mismo pasa con "b". Como ackerman es ahora (Int, Object) y es el valor de retorno de la función Main esta se actualiza correspondientemente. El nodo IF2 también se actualiza por la misma razón. Queda como resulatdo.

```python
class Main {
	main(a:(Int, Object), b:(Int, Object)) : (Int, Object) {
        ackermann(a, b)
    };
	
	ackermann(m : (Int), n: (Int)) : (Int, Object) {
		if (m=0) then n+1 else
			if (n=0) then ackermann(m-1, 1) else
				ackermann(m-1, ackermann(m, n-1))
			fi         
		fi     
	};
    -- Con IF1 siendo(Int, Obj) e IF2 siendo (Int, Object).
};
```
Ahora entra en acción el Type Linker que va a tratar de reemplazar los bolsas de tipos por sus valores más estrictos y siempre que haya algún error, se actualizará para satisfacer los constraints. En este caso probarlo todo con Int no crea ningún conflicto, y por ende queda:

```python
class Main {
	main(a:(Int), b:(Int)) : (Int) {
        ackermann(a, b)
    };
	
	ackermann(m : (Int), n: (Int)) : (Int) {
		if (m=0) then n+1 else
			if (n=0) then ackermann(m-1, 1) else
				ackermann(m-1, ackermann(m, n-1))
			fi         
		fi     
	};
    -- Con IF1 siendo(Int) e IF2 siendo (Int).
};
```

En el proyecto hay una carpeta llamada auto_type_scripts que contiene pequeños ejemplos poniendo en uso las distintas habilidades del inferenciador.