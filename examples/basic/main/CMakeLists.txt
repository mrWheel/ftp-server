#-- SPDX-License-Identifier: GPL-3.0-or-later
#-- Copyright (C) 2026 Willem Aandewiel

idf_component_register(SRCS "main.c" INCLUDE_DIRS "." REQUIRES fatfs mdns wear_levelling)
