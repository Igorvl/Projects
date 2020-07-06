import React from 'react';
import s from '../../../css/Users.module.css';
import ava from '../../../Images/logo.svg';
import Icon24Like from '@vkontakte/icons/dist/24/like';
import Icon24LikeOutline from '@vkontakte/icons/dist/24/like_outline';
import Preloader from "../../Common/Preloader";
import {NavLink} from "react-router-dom";

export default (props) => {
	
	return (
		<div className={s.mainProfile}>
			{props.preloaderOn ? <Preloader/> :
				<div>
					<div className={s.userMain}>
						{props.paginationNums.map(i => <span className={props.choosedPage !== i
							? s.pageNumber
							: s.currentPageNumber} onClick={e => props.selectedPage(i)} key={i}>{i}</span>)}
					</div>
					<div>
						{props.usersData.map(u => {
							return (
								<div className={s.userMain} key={u.id}>
									<NavLink to={'/profile/' + u.id} className={s.userLink}>
										<img className={s.ava} src={u.photos.small !== null ? u.photos.small : ava} alt=""
										     onClick={() => props.choosedUserId(u.id)}/>
									</NavLink>
									<div className={s.userName}>{u.name}</div>
									
									<div>
										{u.follow
											? <Icon24Like className={s.buttonFollow} onClick={() => props.unfollow(u.id)}/>
											: <Icon24LikeOutline className={s.buttonFollow} onClick={() => props.follow(u.id)}/>
										}
									</div>
								</div>
							)
						})}
					</div>
				</div>
			}
		</div>
	);
};

