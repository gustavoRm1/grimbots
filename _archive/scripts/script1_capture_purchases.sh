#!/bin/bash

echo "=============================================="
echo " CAPTURANDO PURCHASES ENVIADOS À META (CAPI)"
echo "=============================================="
echo ""

echo "---- Logs de send_meta_pixel_purchase_event ----"
grep -R "send_meta_pixel_purchase_event" /var/log | tail -n 50

echo ""
echo "---- Requests para graph.facebook.com/events ----"
grep -R "graph.facebook.com" /var/log | grep events | tail -n 20

echo ""
echo "==== FIM ===="
