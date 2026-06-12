# Project Structure
animal-an-erp/
├── README.md
├── requirements.txt
├── main.py
├── config/
│   ├── __init__.py
│   └── settings.py
├── data/
│   └── .gitkeep
├── models/
│   ├── __init__.py
│   ├── base.py    
│   ├── database.py
│   ├── enums.py
│   ├── inventory.py
│   ├── manufacturing.py
│   ├── order.py
│   ├── partner.py
│   ├── payment.py
│   ├── product.py
│   └── user.py
├── viewmodels/
│   ├── __init__.py
│   ├── inventory_vm.py
│   ├── manufacturing_vm.py
│   ├── order_vm.py
│   └── product_vm.py
├── views/
│   ├── __init__.py
│   ├── components/
│   │   ├── __init__.py
│   │   ├── datetime_picker.py
│   │   ├── message_box.py
│   │   └── table_widget.py
│   ├── dialogs/
│   │   ├── __init__.py
│   │   ├── add_material_dialog.py
│   │   ├── manufacturing_dialog.py
│   │   └── order_dialog.py
│   ├── pages/
│   │   ├── __init__.py
│   │   ├── inventory_page.py
│   │   ├── manufacturing_page.py
│   │   ├── order_page.py
│   │   └── product_page.py
│   └── main_window.py
├── utils/
│   ├── __init__.py
│   ├── constants.py
│   ├── database.py
│   ├── logger.py
│   └── validators.py
├── static/
│   ├── icons/
│   │   └── .gitkeep
│   └── styles/
│       └── style.qss
└── logs/
    └── .gitkeep
