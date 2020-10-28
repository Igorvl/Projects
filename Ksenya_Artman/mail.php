<!doctype html>
<html>
<head>
    <meta http-equiv="Content-Type" content="text/html; charset=utf-8" />
<!--     echo "<link rel='stylesheet' href='style.css'>" -->
    
    <title>Ваше сообщение успешно отправлено</title>
</script>

</head>

<body>

<?php
header('Content-Type: text/html; charset=utf-8');

// условный идентификатор формы, для личных нужд
$id_form = 0;

// здесь будет сообщение с ошибкой
$err = '';




// параметры проверяются только если одна из форм активирована
if( !empty($_POST) ) {
    if (isset($_POST['form2'])) {
        $id_form = 2;
/*        echo $_POST['form2'];
        echo 2; // Отладочная метка*/
        
        $name = trim(strip_tags($_POST['name']));
        $phone = trim(strip_tags($_POST['phone']));
        /*$mail = trim(strip_tags($_POST['mail']));*/
        $message = trim(strip_tags($_POST['message']));
    
        mail('mail@igorvl.ru', 'Письмо с Eurolab', 'Из мобильной формы: '.$id_form.'<br />Вам написал: '.$name.'<br />Его номер: '.$phone.'<br />Его сообщение: '.$message,"Content-type:text/html;charset=utf-8");

        echo "Сообщение успешно отправлено!<script>window.location = 'http://diamondwood.ru/XN8XUzg8vDM7A/lp2_test3/default3.html';</script>";
        
/*        echo "<p><a href=\"javascript: history.go(-2)\">Вернуться назад</a></p>";*/
        exit;
    } 
    else if (isset($_POST['form1'])){

        $id_form = 1;
/*        echo 1; // Отладочная метка*/

        $name = trim(strip_tags($_POST['name']));
        $phone = trim(strip_tags($_POST['phone']));
        /*$mail = trim(strip_tags($_POST['mail']));*/
/*        $message = trim(strip_tags($_POST['message']));*/   
    
        mail('mail@igorvl.ru', 'Письмо с Eurolab', 'Из десктопной формы: '.$id_form.'<br />Вам написал: '.$name.'<br />Его номер: '.$phone.'<br />',"Content-type:text/html;charset=utf-8");
/*        echo <link href="./css/euromedialab.css" rel="stylesheet" type = "text/css">*/
/*        echo "<p><font size='6pt'>Ваше сообщение</font><br /><strong><font size='9pt'>отправлено</font></strong><br /><br />Мы ответим Вам в ближайшее время для уточнения всех деталей<br />Вашего заказа<br /><br />Благодарим за обращение!<br /><br /><a href=\"javascript: history.go(0)\">Вернуться назад</a></p>";*/

/*        echo "<script>window.location.replace('http://diamondwood.ru/XN8XUzg8vDM7A/lp2_test3/default3.html');</script>";*/
        echo "Сообщение успешно отправлено!<script>window.location = 'http://diamondwood.ru/XN8XUzg8vDM7A/lp2_test3/default3.html';</script>";
        exit;
    }
    else{
      echo var_dump($_POST['form1']); // Отладочная метка
      echo var_dump($_POST['form2']); // Отладочная метка
      echo var_dump($_POST); // Отладочная метка
    }
}
?>

</body>