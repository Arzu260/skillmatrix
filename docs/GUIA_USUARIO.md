# Guía de usuario

## Roles

| Rol | Puede |
|---|---|
| **RRHH / Administrador** | Todo, incluida la gestión de usuarios, los tokens de otras aplicaciones y los ajustes. |
| **Manager** | Evaluar, dar de alta y modificar empleados, habilidades y puestos, e importar datos. |
| **Solo lectura** | Consultar todo y exportar. |

## La escala

| Nivel | Significado | Orientación |
|:-:|---|---|
| — | Sin evaluar | Todavía nadie ha valorado esta habilidad para esta persona. |
| 0 | No lo conoce | Evaluado: no tiene conocimientos. |
| 1 | Nociones básicas | Sabe qué es y para qué sirve. |
| 2 | Principiante | Hace tareas sencillas con ayuda. |
| 3 | Intermedio | Trabaja de forma autónoma en tareas habituales. |
| 4 | Avanzado | Resuelve problemas complejos y ayuda a otros. |
| 5 | Experto | Referente en la empresa; define buenas prácticas. |

Conviene acordar estas descripciones entre los managers para que las valoraciones sean comparables.

## Resumen

![Resumen](img/resumen.png)

- **Pendientes de revisar**: personas con evaluaciones más antiguas que el plazo configurado, o sin evaluar.
- **Cumplimiento por puesto**: porcentaje medio de lo que exige cada puesto que cumplen sus empleados.
- **Habilidades con menos expertos**: conocimiento concentrado en pocas personas, candidato a formación.
- **Últimos cambios**: quién cambió qué nivel y cuándo, desde la web, la API o una importación.

## Matriz

![Matriz](img/matriz.png)

- **Evaluar**: haz clic en una celda y elige el nivel. Con el teclado, selecciona una celda (Tab o flechas)
  y pulsa un número del 0 al 5.
- **Confirmar que sigue vigente**: pulsa el mismo nivel que ya tiene, o usa *Confirmar nivel con fecha de hoy*
  en el selector. El nivel no cambia, pero se renueva su fecha.
- **Quitar una evaluación**: *Quitar evaluación* en el selector, o la tecla `Supr`.
- **Significado de las marcas**:
  - Celda rayada: evaluación con más antigüedad que el plazo configurado.
  - Punto ámbar: nivel por debajo del que exige el puesto de esa persona.
  - Celda en blanco: sin evaluar.
- **Filtros**: búsqueda por persona o habilidad, departamento, categoría, puesto y *Solo personas con
  evaluaciones antiguas*.

## Ficha de empleado

![Ficha de empleado](img/ficha.png)

Desde la matriz (clic en el nombre) o desde *Empleados*. Muestra el nivel y la fecha de cada evaluación
(en ámbar si está desactualizada), el cumplimiento de su puesto y el historial de cambios.

**Confirmar todos los niveles** renueva la fecha de todas sus evaluaciones sin cambiarlas. Úsalo
después de revisarlas con la persona, por ejemplo en la evaluación anual.

## Puestos y brechas

![Brechas](img/brechas.png)

1. Crea el puesto y marca el nivel mínimo que exige en cada habilidad (0 = no la necesita). Guarda.
2. El análisis muestra el % de cumplimiento de cada persona y cuánto le falta en cada habilidad.
3. Cambia a *Toda la plantilla* para buscar candidatos para ese puesto entre todos los empleados.

## Importar y exportar

- **Exportar**: el Excel incluye la matriz con colores, la hoja *Evaluaciones* con fechas y autores, las
  habilidades y la escala. En CSV se puede elegir el formato matriz o evaluaciones.
- **Importar**: sube un .xlsx o .csv.
  - **Formato matriz**: columnas Código, Nombre, Email, Departamento, Puesto y una columna por habilidad.
    Lo más fácil es exportar, editar y volver a importar. Las celdas vacías no cambian nada.
  - **Formato evaluaciones**: una fila por evaluación con Código o Email, Empleado, Habilidad, Nivel y, opcionalmente,
    Fecha evaluación. Sirve para cargar datos históricos con su fecha real.
  - Por defecto, **reimportar niveles que no cambian no renueva su fecha**, para que un Excel exportado y
    reimportado no haga parecer revisado todo. Marca *Contar como revisados hoy los niveles que no cambian*
    solo si el archivo es el resultado de una revisión completa.

## Administración (solo RRHH)

- **Usuarios**: altas, roles y contraseñas.
- **Aplicaciones (API)**: tokens para las aplicaciones que se conectan a SkillMatrix. El token se muestra una
  sola vez; revócalo cuando la aplicación deje de usarse. Ver la [Guía de la API](API.md).
- **Ajustes**: meses a partir de los cuales una evaluación se considera desactualizada (12 por defecto).
