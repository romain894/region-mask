API reference
=============

Natural Earth preparation
-------------------------

.. autofunction:: region_mask.countries.generate_countries

.. autofunction:: region_mask.oceans.generate_oceans

.. autofunction:: region_mask.merge.generate_merge

.. autofunction:: region_mask.land_ocean.generate_land_ocean

Fractional masks
----------------

.. autofunction:: region_mask.mask.generate_mask

.. autoclass:: region_mask.mask.MaskResult
   :members:

.. autofunction:: region_mask.mask.shift_longitude

.. autofunction:: region_mask.mask.normalize_fractions

Configuration
-------------

.. autofunction:: region_mask.pipeline.environment_settings

.. autofunction:: region_mask.pipeline.run_stage

.. py:data:: region_mask.pipeline.DEFAULTS

   Default stage configuration. Explicit settings override these values.

.. literalinclude:: ../region_mask/pipeline.py
   :language: python
   :start-at: DEFAULTS =
   :end-before: STAGES =
