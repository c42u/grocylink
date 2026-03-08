# Arbeitsanweisung – grocylink

## Erstelldatum - 2026-03-08

### Beschreibung

- Mir ist heute etwas aufgefallen und eingefallen. Die Kassenbons haben ja eine Namen für ein Produkt, in der Regel ist dieser etwas anders als der Name der letztendlich in Grocy gespeichert wird. Der Name wird in Grocylink angepasst, sodass er in Grocy verständlich ist. Um das matching zwischen automatisierten Kassenbon und Grocy über Grocylink zurealisieren, wird eine Datenbank benötigt, die die Kassenbon Produkt mit dem Grocy Produkt matcht und zusammenführt. Erstelle eine solche Datenbank, die die Match-Informationen speichert. Wichtig ist hierbei auch, wenn der BON-NAME unterschiedlich erkannt wird, aber das durch den Nutzer festgelegt Produkt den gleichen Namen hat, dass der BON-Name als mögliche Erkennungssignatur für da Produkt ebenfall in der Datenbank für das Produkt gespeichert wird.

- Bei der "Kassenbon prüfen" Funktion kann über die Suchfunktion das Produkt gesucht werden. Wird ein Produkt gefunden, wird es automatisch mit Bild bereitgestellt. Eine Auswahl ist nicht möglich. Ich hätte gerne eine Auswahl an den gefunden Produkten, da der Vorschlag nicht immer 100% ist, da das Produkt vom Markt abhängig sein kann, bei gleichen Namen. Ich hätte gern den Score zwischen Preis und Zuordnung. Rechts neben Zuordnung hätte ich gern das gefundene Bild mit den Informationen sowie das Dropdown für das Auswahl der weiteren gefundenen Produkte. Des Weiteren sollten noch die Nährwerte mit übernommen werden. Frage, hast du die Möglichleit Benutzerfelder über die Grocy API anlegen, um für eine Produkt eine Nährwerttabelle anzulegen?

- Die Information "aktuell ungetestet" bei Grocylink -> Kanäle -> Gotify kann entfallen und gelöscht werden. Ich habe die Anbindung an Gotify positiv testen können.

---

_Keine offene Arbeitsanweisung._