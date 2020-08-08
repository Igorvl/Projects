import React, {Component} from "react";
import {Layout, Input, Button, List} from "antd";
import {CheckOutlined} from '@ant-design/icons';
import ReactDOM from 'react-dom';

//import Coverflow Carousele
import Coverflow from 'react-coverflow';

//import our firestore module
import firestore from "./firestore";
//import AntD Carousele
import {Carousel} from 'antd';

import "./App.css";

const {Header, Footer, Content} = Layout;

const fn = function () {
	/* do your action */
};

export default class App extends Component {
	constructor(props) {
		super(props);
		// Set the default state of our application
		this.state = {addingTodo: false, pendingTodo: "", todos: []};
		// We want event handlers to share this context
		this.addTodo = this.addTodo.bind(this);
		this.completeTodo = this.completeTodo.bind(this);
		// We listen for live changes to our todos collection in Firebase
		firestore.collection("todos").onSnapshot(snapshot => {
			let todos = [];
			snapshot.forEach(doc => {
				const todo = doc.data();
				todo.id = doc.id;
				if (!todo.completed) todos.push(todo);
			});
			// Sort our todos based on time added
			todos.sort(function (a, b) {
				return (
					new Date(a.createdAt).getTime() - new Date(b.createdAt).getTime()
				);
			});
			// Anytime the state of our database changes, we update state
			this.setState({todos});
		});
	}
	
	async completeTodo(id) {
		// Mark the todo as completed
		await firestore
			.collection("todos")
			.doc(id)
			.set({
				completed: true
			});
	}
	
	async addTodo() {
		if (!this.state.pendingTodo) return;
		// Set a flag to indicate loading
		this.setState({addingTodo: true});
		// Add a new todo from the value of the input
		await firestore.collection("todos").add({
			content: this.state.pendingTodo,
			completed: false,
			createdAt: new Date().toISOString()
		});
		// Remove the loading flag and clear the input
		this.setState({addingTodo: false, pendingTodo: ""});
	}
	
	
	render() {
		return (
			<Layout className="App">
				<Header className="App-header">
					<h1>Quick Todo</h1>
				</Header>
				<Content className="App-content">
					<Input
						ref="add-todo-input"
						className="App-add-todo-input"
						size="large"
						placeholder="What needs to be done?"
						disabled={this.state.addingTodo}
						onChange={evt => this.setState({pendingTodo: evt.target.value})}
						value={this.state.pendingTodo}
						onPressEnter={this.addTodo}
						required
					/>
					<Button
						className="App-add-todo-button"
						size="large"
						type="primary"
						onClick={this.addTodo}
						loading={this.state.addingTodo}
					>
						Add Todo
					</Button>
					<List
						className="App-todos"
						size="large"
						bordered
						dataSource={this.state.todos}
						renderItem={todo => (
							<List.Item>
								{todo.content}
								<CheckOutlined
									onClick={evt => this.completeTodo(todo.id)}
									className="App-todo-complete"
								/>
							</List.Item>
						)}
					/>
					
					<div className="CarouselContainer">
						<Carousel autoplay effect="fade">
							<div>
								<h3 className="CarouselStyle"> 1 <CheckOutlined/></h3>
							</div>
							<div>
								<h3 className="CarouselStyle"> 2 <CheckOutlined/></h3>
							</div>
							<div>
								<h3 className="CarouselStyle"> 3 <CheckOutlined/></h3>
							</div>
							<div>
								<h3 className="CarouselStyle"> 4 <CheckOutlined/></h3>
							</div>
						</Carousel>
					</div>
					
					
					
					<Coverflow width="960" height="500" classes={{background: 'rgb(233, 23, 23)'}} className=''
					           displayQuantityOfSide={2}
					           navigation={false}
					           enableScroll={true}
					           clickable={true}
					           active={0}
					>
						<div
							onClick={() => fn()}
							onKeyDown={() => fn()}
							role="menuitem"
							tabIndex="0"
						>
							<img
								src='image/path'
								alt='title or description'
								style={{
									display: 'block',
									width: '100%',
								}}
							/>
						</div>
						<img src='image/path' alt='title or description' data-action="http://andyyou.github.io/react-coverflow/"/>
						<img src='image/path' alt='title or description' data-action="http://andyyou.github.io/react-coverflow/"/>
					</Coverflow>
				
				</Content>
				<Footer className="App-footer">&copy; My Company</Footer>
			</Layout>
		
		);
	}
}