import React from 'react';
import preloader from '../Common/preloader.svg';
import s from '../../css/Users.module.css';

export default () => {
	return (
		<div className={s.preloaderBox}><img src={preloader} alt=""/></div>
	);
};