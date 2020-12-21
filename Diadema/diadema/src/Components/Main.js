import React from 'react';
import '../styles/Main.css';
import diadema from '../img/Diadema.png';
import diademaSimbol from '../img/diademaSimbol.png';
import ph_Anna from '../img/ph_Anna.webp';
import ph_Ally from '../img/ph_Ally.webp';
import ph_fairy from '../img/ph_fairy.webp';
import ph_Lilli from '../img/ph_Lilli.webp';
import ph_Rose from '../img/ph_Rose.webp';
import ph_magic from '../img/ph_magic.webp';
import bootsFor from '../img/bootsFor.webp';

export default () => {
	return (
		<section className="main">
			<div className="grid-container">
				<div className="Top-Menu">
					<div className="TopMenu-Logo">
						<img src={diadema} alt="Diadema"/>
					</div>
					<div className="TopMenu-Menu">
						<ul>
							<li><a className="TopMenu-Link" href='#'>ГЛАВНАЯ</a></li>
							<li><a className="TopMenu-Link" href='#'>КАТАЛОГ</a></li>
							<li><a className="TopMenu-Link" href='#'>ПОДАРКИ И СКИДКИ</a></li>
							<li><a className="TopMenu-Link" href='#'>О САЛОНЕ</a></li>
							<li><a className="TopMenu-Link" href='#'>КОЛЛЕКЦИИ</a></li>
							<li><a className="TopMenu-Link" href='#'>КОНТАКТЫ</a></li>
						</ul>
					</div>
					<div className="TopMenu-Phone">
						<span>8/<span className='PhoneCode'>495</span>/ 761-32-99</span>
						<span>Звоните с 11:00 до 21:00</span>
					</div>
				</div>
				<div className="Diadema">
					<div className="Diadema-Simbol">
						<img src={diademaSimbol} alt=""/>
					</div>
				</div>
				<div className="Sale">
					<div className="Sale-Title">
						<h1>Распродажа платьев и аксессуаров</h1>
						<span className="Sale-Title_txt">
						До 1 апреля Свадебные аксессуары и платья со скидкой 50%
					</span>
						<span className="Sale-Title_code">
						код: <span>50SALE</span>
					</span>
					</div>
					<div className="Sale-Items">
						<div className="Item">
							<div className="Item-Photo">
								<img src={ph_Anna} alt="ph_Anna"/>
							</div>
							<div className="Item-Price">
								Принцесса Анна
								<span>5500р</span>
							</div>
						</div>
						<div className="Item">
							<div className="Item-Photo">
								<img src={ph_Ally} alt="ph_Ally"/>
							</div>
							<div className="Item-Price">
								Маленькая Элли
								<span>6000р</span>
							</div>
						</div>
						<div className="Item">
							<div className="Item-Photo">
								<img src={ph_magic} alt="ph_magic"/>
							</div>
							<div className="Item-Price">
								Волшебное платье
								<span>5800р</span>
							</div>
						</div>
						<div className="Item">
							<div className="Item-Photo">
								<img src={ph_Lilli} alt="ph_Lilli"/>
							</div>
							<div className="Item-Price">
								Платье Лиллии
								<span>4500р</span>
							</div>
						</div>
						<div className="Item">
							<div className="Item-Photo">
								<img src={ph_Rose} alt="ph_Rose"/>
							</div>
							<div className="Item-Price">
								Принцесса Роза
								<span>5500р</span>
							</div>
						</div>
						<div className="Item">
							<div className="Item-Photo">
								<img src={ph_fairy} alt="ph_fairy"/>
							</div>
							<div className="Item-Price">
								Платье Феи
								<span>4500р</span>
							</div>
						</div>
					</div>
				</div>
				<div className="Celebrate">
					<div className="Celebrate-Text">
						<h1>Праздничные детские платья</h1>
						<span>В нашем салоне "Диадема" наряду со свадебными платьями представлены <u>новые коллекции</u> детских праздничных, красивых платьев для девочек. В наших коллекциях отражены все направления современной детской нарядной	моды.</span>
					</div>
					<div className="Celebrate-Filter">
						<a href="#" className="filterLink">
							<div className="filter">
								платья до 1 года
							</div>
						</a>
						<a href="#" className="filterLink">
							<div className="filter">
								платья 2-3 года
							</div>
						</a>
						<a href="#" className="filterLink">
							<div className="filter">
								платья 3-4 года
							</div>
						</a>
						<a href="#" className="filterLink">
							<div className="filter">
								платья 5-6 лет
							</div>
						</a>
					</div>
				</div>
				<div className="HelpChoose">
					<div className="HelpChoose-Shoes">
						<h1>Поможем подобрать платье</h1>
					</div>
					<div className="HelpChoose-Txt">
						<div className="ChooseTxt">Наши специалисты с удовольствием покажут и помогут подобрать платья по Вашему
							вкусу. Дети растут очень быстро и так же быстро вырастают из своих обнов. <br/>Учитывая это, цены на наши
							платья доступны всем. А добиваемся мы этого за счет того, что наши изготовители до минимума сократили
							отходы кроя.
						</div>
					</div>
					<div className="HelpChoose-Form">
						<h1>Получите <br/>подарок</h1>
						<form action="#" className='ChooseForm'>
							<div className="fieldWrap">
								<textarea type='text' name="field1" id="field1" cols="20" rows="1" className='FormField'></textarea>
							</div>
							<div className='fieldWrap'>
								<textarea type='text' name="field2" id="field2" cols="20" rows="1" className='FormField'></textarea>
							</div>
							<button className='FormButton'>ПОЛУЧИТЬ</button>
						</form>
						<span>Ваши данные будут использоваться только для связи с Вами.</span>
					</div>
					<div className='HelpChoose-Img'>
						<img src={bootsFor} alt="bootsFor" className='bootsFor'/>
					</div>
				</div>
				<div className="ChooseWithUs">
					<div className="ChooseWithUs-Txt">
						<h1>Выбирайте платье вместе с нами</h1>
						<span>Стоя перед зеркалом в разных ракурсах Ваша девочка представляет себя и принцессой, и золушкой, и невестой,
						и балериной.</span>
					</div>
					<div className="ChooseWithUs-Phone">
						8/495/ 761-32-99
						Москва, ул. Ленинский проспект, дом 40
					</div>
				</div>
				<div className="Copyright">
					© 2010–2022 Компания «Диадема» Платья для настоящих принцесс
				</div>
			</div>
		
		</section>
	)
}