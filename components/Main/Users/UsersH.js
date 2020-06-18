import React, {useState} from 'react';
import s from '../../../css/Users.module.css';
import ava from '../../../Images/logo.svg';
import Icon24Like from '@vkontakte/icons/dist/24/like';
import Icon24LikeOutline from '@vkontakte/icons/dist/24/like_outline';
import * as axios from 'axios';

export default (props) => {
	// хук для запроса на серв.
	let [initialState, axiosResponse] = useState();
	//если длина списка пользователей === 0 делается запрос на сервер и производится запись пришедшего списка через CB
	axiosResponse = (props.usersData.length === 0) || (props.currentPage !== props.choosedPage) ? axios.get(`https://social-network.samuraijs.com/api/1.0/users?count=${props.usersOnPage}&page=${props.choosedPage}`).then(response => {
		props.getUsersCB(response.data);
	}) : null;
	
	let paginationNums = [];
	for (let i = 1; i <= props.totalPages; i++) {
		paginationNums.push(i);
	}
	
	return (
		<div className={s.mainProfile}>
			<div className={s.userMain} >
				{paginationNums.map(i => <span className={props.choosedPage !== i ? s.pageNumber : s.currentPageNumber}
				                               onClick={e => props.choosedPageCB(i)} key={i}>{i}</span>)
				}
			</div>
			<div>
				{props.usersData.map(u => {
					return (
						<div className={s.userMain} key={u.id}>
							<img className={s.ava} src={u.photos.small !== null ? u.photos.small : ava} alt=""/>
							<div>{u.name}</div>
							<div>
								{u.follow
									? <Icon24Like className={s.buttonFollow} onClick={() => props.unfollowCB(u.id)}/>
									: <Icon24LikeOutline className={s.buttonFollow} onClick={() => props.followCB(u.id)}/>
								}
							</div>
						</div>
					)
				})}
			</div>
		</div>
	);
};

