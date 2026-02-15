ANTLR4 Grammar
==============

Fileseq v3 uses an ANTLR4 grammar for parsing file sequences. This grammar is shared across Python, Go, and C++ implementations to ensure consistent behavior.

Grammar File
------------

The complete grammar is defined in ``src/fileseq/grammar/fileseq.g4``:

.. literalinclude:: ../src/fileseq/grammar/fileseq.g4
   :language: antlr
   :linenos:

Regenerating the Parser
-----------------------

If you modify the grammar, regenerate the Python parser:

.. code-block:: bash

   # Using hatch
   hatch run generate

   # Or directly with Java
   java -jar tools/antlr-4.13.1-complete.jar \
       -Dlanguage=Python3 \
       -visitor \
       -o src/fileseq/parser \
       src/fileseq/grammar/fileseq.g4

Requirements:
  - Java 11+ in PATH
  - ANTLR 4.13.1 JAR (included in ``tools/``)

Grammar Rules
-------------

The grammar defines four main patterns:

**sequence**
  Full sequence with frame range and padding: ``/path/file.1-100#.exr``

**patternOnly**
  Padding without explicit frame range: ``/path/file.#.exr``

**singleFrame**
  Single frame file: ``/path/file.0100.exr``

**plainFile**
  No frame pattern: ``/path/file.txt``

Python-Specific Features
------------------------

The Python implementation supports additional subframe notation:

- Dual range: ``file.1-5#.10-20@@.exr`` (main frames + subframes)
- Composite padding: ``file.1-5@.#.exr`` (frame + subframe padding)
- Pattern only: ``file.#.#.exr`` (wildcard for both components)

These patterns are parsed by the grammar but ignored by Go/C++ implementations until subframe support is added.
