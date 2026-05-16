from docling.datamodel.pipeline_options import PdfPipelineOptions, AcceleratorOptions
opts = PdfPipelineOptions()
opts.accelerator_options = AcceleratorOptions(num_threads=2)
opts.ocr_batch_size = 2
opts.layout_batch_size = 2
opts.table_batch_size = 2
print('OK', opts.accelerator_options)
