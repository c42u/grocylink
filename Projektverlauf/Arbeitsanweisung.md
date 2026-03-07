# Arbeitsanweisung – grocylink

Bei einem Netto Kassenbon steht die Anzahl der Produkt in der Zeile über dem Produktnamen. 
Hier ist eine Anpassung in der Bon-Analyse notwendig, da dies nicht berücksichtig wird. 
Es wird lediglich das Produkt mit der Gesamtsummer ausgegeben.;
Beim Aldi Kassenbon sind Produkte alle Produkt einzeln aufgeführt.
Dadurch taucht das gleiche Produkt mehrmals auf einem Kassenbon auf und somit auch im Kassenbon Import von groylink.
Es wäre gut, wenn hier eine Prüfung erfolgen würde, von Produkten mit gleichem Namen auf einem Kassenbon und dies dann auch beim Import berücksichtig wird.;
Wir haben das Thema Barcode für die Produkte noch offen, wenn die Produkte noch nicht angelegt sind.
Ich hab zwar gesehen, dass eine Suchfunktion implementiert ist, da passiert aber nicht. Ich habe mal geschaut.
Es gibt diese Internetseiten

  - https://opengtindb.org/
  - https://de.openfoodfacts.org/data
  - https://www.ean-suche.de/
  - https://www.ean-search.org/
  - https://go-upc.com/
  - https://www.barcodelookup.com/api

bei denen Barcode für Produkt abgefragt werden können, kannst du das Implementieren, 
wenn ein Produkt über den Kassbon Import dazu kommt, es neu ist oder in grocy kein barcode vorhanden ist
dies automatisch geprüft wird und ein Vorschlag-Dropdown angezeigt wird.


---